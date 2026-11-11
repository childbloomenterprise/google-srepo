import json
import mimetypes
import os
import re
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from app.models import Letters, Verdict, VoiceResult
from app.rules import load_rulebook

DEFAULT_ANALYSIS_CHAIN = (
    "gemini-4-argon,gemini-3.8-flash,gemini-3.6-flash,"
    "gemini-3-flash-preview,gemini-3.5-flash,gemini-3.1-flash-lite"
)
DEFAULT_FAST_CHAIN = (
    "gemini-3.8-flash,gemini-3.6-flash,gemini-3-flash-preview,gemini-3.1-flash-lite"
)
QUARANTINE_TTL_SECONDS = 10 * 60
_QUARANTINED_MODELS: dict[str, float] = {}

ANALYSIS_PROMPT = """Review the supplied Indian health-insurance policy, hospital records, and
insurer decision. Return the requested structured verdict.

Use only rules in the rulebook. Quote evidence verbatim from the supplied documents. Mark a
refusal VALID when it is genuinely supported, such as a real exclusion or real non-disclosure
within 60 months. Never suggest hiding facts. Always fill amounts in INR. Do not invent facts,
policy clauses, dates, or evidence. If a fact is unavailable, use null or add it to missing_info.
Evaluate every distinct refused or deducted line item separately. Different reasons applied to the
same denied charge are grounds for one refusal, not duplicate monetary items: combine the supported
reasons and rule IDs, count that denied amount only once, and never make refusal amounts exceed the
unique denied amount. Keep genuinely separate deductions as separate items.
For a room-rent proportionate deduction, check each item under R06: it is never allowed on pharmacy
or consumables, implants or medical devices, diagnostics, or ICU charges, and is not allowed when
the hospital does not use differential room-based billing for that item. Do not cite R11 based only
on the insurer calling a condition pre-existing; the documents must give a diagnosis or treatment
date that can be compared with the first policy start. If no such date is documented, or records
say no diagnosis or treatment is recorded, omit R11. For non-disclosure after at least 60 months of
continuous cover, assess the allegation under R01. For each refusal, only cite rules the uploaded
documents support.
Keep each plain-language explanation to no more than two simple sentences. The policyholder may have
a STRONG/WEAK case; assess fairly and do not assume every deduction is wrongful.
Return all dates as YYYY-MM-DD, converting the document's displayed date format as needed.
"""


class GeminiService:
    def __init__(self, client: Any | None = None):
        self._client = client

    @property
    def client(self) -> Any:
        if self._client is None:
            api_key = os.getenv("GEMINI_API_KEY")
            if not api_key and os.getenv("APP_ENV", "development") != "production":
                key_path = Path("/home/ubuntu/.gemini_key")
                if key_path.exists():
                    api_key = key_path.read_text(encoding="utf-8").strip()
            if not api_key:
                raise RuntimeError("GEMINI_API_KEY is required")
            self._client = genai.Client(api_key=api_key)
        return self._client

    @staticmethod
    def _status_code(exc: Exception) -> int | None:
        code = getattr(exc, "code", None)
        try:
            if code is not None:
                return int(code)
        except (TypeError, ValueError):
            pass
        match = re.match(r"^\s*(\d{3})\b", str(exc))
        return int(match.group(1)) if match else None

    @staticmethod
    def _model_chain(chain_env: str, default: str, legacy_env: str) -> list[str]:
        configured = os.getenv(chain_env, default)
        models = [model.strip() for model in configured.split(",") if model.strip()]
        legacy_model = os.getenv(legacy_env, "").strip()
        if legacy_model:
            models.insert(0, legacy_model)
        return list(dict.fromkeys(models))

    @staticmethod
    def _is_quarantined(model: str) -> bool:
        expires_at = _QUARANTINED_MODELS.get(model)
        if expires_at is None:
            return False
        if expires_at > time.monotonic():
            return True
        del _QUARANTINED_MODELS[model]
        return False

    def _generate(
        self,
        *,
        contents: list[Any],
        schema: type,
        system_instruction: str,
        chain_env: str,
        default_chain: str,
        legacy_env: str,
    ) -> tuple[Any, str]:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=schema,
        )
        models = self._model_chain(chain_env, default_chain, legacy_env)
        last_error: Exception | None = None
        for model in models:
            if self._is_quarantined(model):
                continue
            for attempt in range(2):
                try:
                    response = self.client.models.generate_content(
                        model=model, contents=contents, config=config
                    )
                    return response, model
                except Exception as exc:
                    last_error = exc
                    status = self._status_code(exc)
                    if status == 429:
                        _QUARANTINED_MODELS[model] = (
                            time.monotonic() + QUARANTINE_TTL_SECONDS
                        )
                        break
                    if status == 404:
                        break
                    if status in {500, 502, 503, 504} and attempt == 0:
                        time.sleep(2)
                        continue
                    break
        if last_error is not None:
            raise last_error
        raise RuntimeError("No configured Gemini models are currently available")

    @staticmethod
    def _parse_response(response: Any, schema: type) -> Any:
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            return schema.model_validate(parsed)
        text = getattr(response, "text", None)
        if not text:
            raise ValueError("Gemini returned no structured response")
        return schema.model_validate(json.loads(text))

    def analyze(
        self, documents: list[tuple[str, bytes]], notes: str = ""
    ) -> tuple[Verdict, str]:
        contents: list[Any] = []
        for filename, data in documents:
            mime_type = mimetypes.guess_type(filename)[0] or "application/octet-stream"
            contents.append(types.Part.from_bytes(data=data, mime_type=mime_type))
        contents.append(
            "Policyholder notes (may be empty):\n"
            + (notes.strip() or "[No additional notes]")
            + "\n\nExtract the case facts and assess each distinct refused or deducted item."
        )
        system_instruction = f"{ANALYSIS_PROMPT}\n\nCURATED IRDAI RULEBOOK:\n{load_rulebook()}"
        response, model_used = self._generate(
            contents=contents,
            schema=Verdict,
            system_instruction=system_instruction,
            chain_env="CB_MODEL_CHAIN_ANALYSIS",
            default_chain=DEFAULT_ANALYSIS_CHAIN,
            legacy_env="CB_MODEL_ANALYSIS",
        )
        return self._parse_response(response, Verdict), model_used

    def generate_letters(self, case: dict[str, Any]) -> tuple[Letters, str]:
        allowed_rules = sorted(
            {
                rule_id
                for refusal in case["refusals"]
                for rule_id in refusal["rule_ids"]
            }
            | ({case["interest_rule_id"]} if case.get("interest_rule_id") else set())
        )
        prompt = f"""Draft two plain-text documents for this policyholder using the supplied case.
Use the policyholder's own name and first-person voice. If their name is unavailable, include
`[Please add your full name]` rather than inventing one. Cite only these verified rule IDs:
{", ".join(allowed_rules) if allowed_rules else "No rule IDs were verified"}
Do not cite any other rules or invent legal facts. Include a clear requested resolution.

The Insurance Ombudsman complaint must include all Rule 14(2) fields: complainant name and
address, insurer branch, facts, documents relied upon, nature and extent of loss, and relief sought.
For unavailable postal address or insurer branch, include a clearly labelled [Please add ...]
placeholder rather than inventing one. State that the draft is for the policyholder to send.

Case facts and verified findings:
{json.dumps(case, ensure_ascii=False)}
"""
        response, model_used = self._generate(
            contents=[prompt],
            schema=Letters,
            system_instruction=(
                "You draft accurate first-person insurance grievance documents. Do not add "
                "unverified facts, legal advice, or legal representation claims."
            ),
            chain_env="CB_MODEL_CHAIN_ANALYSIS",
            default_chain=DEFAULT_ANALYSIS_CHAIN,
            legacy_env="CB_MODEL_ANALYSIS",
        )
        return self._parse_response(response, Letters), model_used

    def transcribe(self, data: bytes, mime_type: str) -> tuple[VoiceResult, str]:
        response, model_used = self._generate(
            contents=[
                types.Part.from_bytes(data=data, mime_type=mime_type),
                "Transcribe the speaker in Hindi or English as spoken, then extract the available "
                "insurance facts. Do not infer missing values.",
            ],
            schema=VoiceResult,
            system_instruction=(
                "Accurately transcribe policyholder voice messages and extract only stated facts."
            ),
            chain_env="CB_MODEL_CHAIN_FAST",
            default_chain=DEFAULT_FAST_CHAIN,
            legacy_env="CB_MODEL_FAST",
        )
        return self._parse_response(response, VoiceResult), model_used
