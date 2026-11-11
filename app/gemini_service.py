import json
import mimetypes
import os
import time
from pathlib import Path
from typing import Any

from google import genai
from google.genai import types

from app.models import Letters, Verdict, VoiceResult
from app.rules import load_rulebook

ANALYSIS_PROMPT = """Review the supplied Indian health-insurance policy, hospital records, and
insurer decision. Return the requested structured verdict.

Use only rules in the rulebook. Quote evidence verbatim from the supplied documents. Mark a
refusal VALID when it is genuinely supported, such as a real exclusion or real non-disclosure
within 60 months. Never suggest hiding facts. Always fill amounts in INR. Do not invent facts,
policy clauses, dates, or evidence. If a fact is unavailable, use null or add it to missing_info.
For each refusal, only cite a rule when the uploaded documents support that rule's applicability.
Keep each plain-language explanation to no more than two simple sentences. The policyholder may
have a STRONG/WEAK case; assess fairly and do not assume every deduction is wrongful.
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

    def _generate(
        self,
        *,
        contents: list[Any],
        schema: type,
        system_instruction: str,
        preferred_model: str,
        fallback: bool = False,
    ) -> Any:
        config = types.GenerateContentConfig(
            system_instruction=system_instruction,
            response_mime_type="application/json",
            response_schema=schema,
        )

        def generate_with_retry(model: str) -> Any:
            for attempt in range(2):
                try:
                    return self.client.models.generate_content(
                        model=model, contents=contents, config=config
                    )
                except Exception as exc:
                    status = str(exc).lstrip().split(maxsplit=1)[0].rstrip(":")
                    if attempt or status not in {"429", "500", "502", "503", "504"}:
                        raise
                    time.sleep(1)

        try:
            return generate_with_retry(preferred_model)
        except Exception:
            fallback_model = os.getenv("CB_MODEL_FAST", "gemini-3.8-flash")
            if not fallback or preferred_model == fallback_model:
                raise
            return generate_with_retry(fallback_model)

    @staticmethod
    def _parse_response(response: Any, schema: type) -> Any:
        parsed = getattr(response, "parsed", None)
        if parsed is not None:
            return schema.model_validate(parsed)
        text = getattr(response, "text", None)
        if not text:
            raise ValueError("Gemini returned no structured response")
        return schema.model_validate(json.loads(text))

    def analyze(self, documents: list[tuple[str, bytes]], notes: str = "") -> Verdict:
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
        response = self._generate(
            contents=contents,
            schema=Verdict,
            system_instruction=system_instruction,
            preferred_model=os.getenv("CB_MODEL_ANALYSIS", "gemini-4-argon"),
            fallback=True,
        )
        return self._parse_response(response, Verdict)

    def generate_letters(self, case: dict[str, Any]) -> Letters:
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
        response = self._generate(
            contents=[prompt],
            schema=Letters,
            system_instruction=(
                "You draft accurate first-person insurance grievance documents. Do not add "
                "unverified facts, legal advice, or legal representation claims."
            ),
            preferred_model=os.getenv("CB_MODEL_ANALYSIS", "gemini-4-argon"),
            fallback=True,
        )
        return self._parse_response(response, Letters)

    def transcribe(self, data: bytes, mime_type: str) -> VoiceResult:
        response = self._generate(
            contents=[
                types.Part.from_bytes(data=data, mime_type=mime_type),
                "Transcribe the speaker in Hindi or English as spoken, then extract the available "
                "insurance facts. Do not infer missing values.",
            ],
            schema=VoiceResult,
            system_instruction=(
                "Accurately transcribe policyholder voice messages and extract only stated facts."
            ),
            preferred_model=os.getenv("CB_MODEL_FAST", "gemini-3.8-flash"),
        )
        return self._parse_response(response, VoiceResult)
