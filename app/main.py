import json
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ValidationError

from app.gemini_service import GeminiService
from app.models import Verdict
from app.rules import load_rulebook
from app.store import CaseStore, create_store
from app.verdict import derive_verdict

ROOT = Path(__file__).resolve().parent.parent
DEMO_ROOT = Path(__file__).with_name("demo")
DEMO_CACHE_ROOT = Path(__file__).with_name("demo_cache")
ALLOWED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".pdf"}
MAX_FILES = 8
MAX_TOTAL_BYTES = 20 * 1024 * 1024


class StatusUpdate(BaseModel):
    event: Literal["grievance_sent", "insurer_replied", "ombudsman_filed", "paid"]
    date: str | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def create_app(
    store: CaseStore | None = None,
    gemini_service: GeminiService | None = None,
    demo_cache_dir: str | Path | None = None,
) -> FastAPI:
    application = FastAPI(title="ClaimBack", version="1.0.0")
    application.state.store = store or create_store()
    application.state.gemini = gemini_service or GeminiService()
    application.state.demo_cache_dir = Path(demo_cache_dir or DEMO_CACHE_ROOT)
    application.mount("/static", StaticFiles(directory=ROOT / "static"), name="static")

    def get_case(case_id: str) -> dict[str, Any]:
        case = application.state.store.get(case_id)
        if not case:
            raise HTTPException(status_code=404, detail="Case not found")
        return case

    def persist_case(
        files: list[tuple[str, bytes]],
        lang: str,
        source: str,
        verdict: Verdict,
        model_used: str,
        cached: bool = False,
        cached_at: str | None = None,
    ) -> dict[str, Any]:
        created_at = utc_now().isoformat()
        result = derive_verdict(verdict, created_at)
        case = {
            "id": str(uuid.uuid4()),
            "created_at": created_at,
            "lang": lang,
            "source": source,
            "documents": [name for name, _ in files],
            "letters": None,
            "tracker_events": [],
            "model_used": model_used,
            "cached": cached,
            "cached_at": cached_at,
            **result,
        }
        application.state.store.save(case)
        return case

    def create_case(
        files: list[tuple[str, bytes]], notes: str, lang: str, source: str = "upload"
    ) -> dict[str, Any]:
        try:
            verdict, model_used = application.state.gemini.analyze(files, notes)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Document analysis failed: {exc}") from exc
        return persist_case(files, lang, source, verdict, model_used)

    def save_demo_cache(case_id: str, verdict: Verdict, model_used: str) -> str:
        cached_at = utc_now().isoformat()
        cache_dir = application.state.demo_cache_dir
        cache_dir.mkdir(parents=True, exist_ok=True)
        cache_payload = {
            **verdict.model_dump(),
            "model_used": model_used,
            "cached_at": cached_at,
        }
        (cache_dir / f"{case_id}.json").write_text(
            json.dumps(cache_payload, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        return cached_at

    def read_demo_cache(case_id: str) -> tuple[Verdict, str, str] | None:
        cache_path = application.state.demo_cache_dir / f"{case_id}.json"
        try:
            payload = json.loads(cache_path.read_text(encoding="utf-8"))
            model_used = payload.pop("model_used")
            cached_at = payload.pop("cached_at")
            verdict = Verdict.model_validate(payload)
            if not isinstance(model_used, str) or not isinstance(cached_at, str):
                return None
            return verdict, model_used, cached_at
        except (OSError, json.JSONDecodeError, KeyError, ValidationError):
            return None

    @application.get("/", response_class=HTMLResponse)
    def home() -> FileResponse:
        return FileResponse(ROOT / "static" / "index.html")

    @application.get("/dashboard", response_class=HTMLResponse)
    def dashboard() -> FileResponse:
        return FileResponse(ROOT / "static" / "index.html")

    @application.get("/healthz")
    def healthz() -> dict[str, str]:
        return {"status": "ok"}

    @application.post("/api/cases")
    async def analyze_case(
        files: list[UploadFile] = File(default=[], alias="files[]"),
        notes: str = Form(default=""),
        lang: Literal["en", "hi"] = Form(default="en"),
    ) -> dict[str, Any]:
        if not files:
            raise HTTPException(status_code=400, detail="Upload at least one document")
        if len(files) > MAX_FILES:
            raise HTTPException(status_code=413, detail=f"Upload no more than {MAX_FILES} files")
        documents: list[tuple[str, bytes]] = []
        total_size = 0
        for upload in files:
            filename = upload.filename or "document"
            if Path(filename).suffix.lower() not in ALLOWED_EXTENSIONS:
                raise HTTPException(status_code=415, detail="Use JPG, PNG, or PDF documents")
            data = await upload.read()
            total_size += len(data)
            if total_size > MAX_TOTAL_BYTES:
                raise HTTPException(
                    status_code=413, detail="Combined file size cannot exceed 20 MB"
                )
            documents.append((filename, data))
        return create_case(documents, notes, lang)

    @application.post("/api/demo/{case_id}")
    def demo_case(case_id: str, request: Request) -> dict[str, Any]:
        if case_id not in {"partial-cut", "ped-rejection"}:
            raise HTTPException(status_code=404, detail="Demo case not found")
        directory = DEMO_ROOT / case_id
        documents = [
            (path.name, path.read_bytes())
            for path in sorted(directory.glob("*.png"))
        ]
        if len(documents) != 3:
            raise HTTPException(status_code=500, detail="Synthetic demo documents are missing")
        lang = request.query_params.get("lang", "en")
        if lang not in {"en", "hi"}:
            raise HTTPException(status_code=422, detail="lang must be en or hi")
        try:
            verdict, model_used = application.state.gemini.analyze(documents, "")
        except Exception as exc:
            cached = read_demo_cache(case_id)
            if cached is None:
                raise HTTPException(
                    status_code=502, detail=f"Document analysis failed: {exc}"
                ) from exc
            verdict, model_used, cached_at = cached
            return persist_case(
                documents,
                lang,
                f"demo:{case_id}",
                verdict,
                model_used,
                cached=True,
                cached_at=cached_at,
            )
        cached_at = save_demo_cache(case_id, verdict, model_used)
        return persist_case(
            documents,
            lang,
            f"demo:{case_id}",
            verdict,
            model_used,
            cached_at=cached_at,
        )

    @application.get("/api/cases/{case_id}")
    def read_case(case_id: str) -> dict[str, Any]:
        return get_case(case_id)

    @application.post("/api/cases/{case_id}/letters")
    def make_letters(case_id: str) -> dict[str, Any]:
        case = get_case(case_id)
        try:
            letters, model_used = application.state.gemini.generate_letters(case)
        except Exception as exc:
            raise HTTPException(status_code=502, detail=f"Letter generation failed: {exc}") from exc
        case["letters"] = letters.model_dump()
        case["letters_model_used"] = model_used
        application.state.store.save(case)
        return {**case["letters"], "model_used": model_used}

    @application.post("/api/voice")
    async def voice(request: Request) -> dict[str, Any]:
        data = await request.body()
        if not data:
            raise HTTPException(status_code=400, detail="Audio is required")
        if len(data) > 20 * 1024 * 1024:
            raise HTTPException(status_code=413, detail="Audio cannot exceed 20 MB")
        content_type = request.headers.get("content-type", "audio/webm").split(";")[0]
        if content_type not in {"audio/webm", "audio/ogg", "audio/wav", "audio/x-wav"}:
            raise HTTPException(status_code=415, detail="Use webm, ogg, or wav audio")
        try:
            result, model_used = application.state.gemini.transcribe(data, content_type)
        except Exception as exc:
            raise HTTPException(
                status_code=502, detail=f"Voice transcription failed: {exc}"
            ) from exc
        return {**result.model_dump(), "model_used": model_used}

    @application.patch("/api/cases/{case_id}/status")
    def patch_status(case_id: str, update: StatusUpdate) -> dict[str, Any]:
        case = get_case(case_id)
        event_date = update.date or date.today().isoformat()
        try:
            date.fromisoformat(event_date)
        except ValueError as exc:
            raise HTTPException(status_code=422, detail="date must be YYYY-MM-DD") from exc
        case["tracker_events"].append(
            {"event": update.event, "date": event_date, "label": update.event.replace("_", " ")}
        )
        if update.event == "insurer_replied":
            case["ombudsman_reply_deadline"] = (
                date.fromisoformat(event_date) + timedelta(days=365)
            ).isoformat()
        application.state.store.save(case)
        return case

    @application.get("/api/dashboard")
    def dashboard_stats() -> dict[str, Any]:
        cases = application.state.store.all()
        citations: dict[str, int] = {}
        for case in cases:
            for refusal in case.get("refusals", []):
                for rule_id in refusal.get("rule_ids", []):
                    citations[rule_id] = citations.get(rule_id, 0) + 1
        most_cited = sorted(citations.items(), key=lambda pair: (-pair[1], pair[0]))[:5]
        return {
            "cases_analysed": len(cases),
            "amount_refused": round(sum(case.get("refused_total", 0) for case in cases), 2),
            "amount_recoverable_flagged": round(
                sum(case.get("recoverable_amount", 0) for case in cases), 2
            ),
            "most_cited_rules": [{"rule_id": key, "count": value} for key, value in most_cited],
            "label": "BigQuery export in production",
        }

    @application.get("/api/rules")
    def rules() -> dict[str, str]:
        return {"rulebook": load_rulebook()}

    return application


app = create_app()
