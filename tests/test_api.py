import json

from fastapi.testclient import TestClient

from app.main import create_app
from app.models import Letters, Refusal, Verdict
from app.store import SqliteCaseStore


class MockGemini:
    def __init__(self):
        self.analysis_calls = 0
        self.letter_calls = 0

    def analyze(self, documents, notes=""):
        self.analysis_calls += 1
        if any("ped-rejection" in filename for filename, _ in documents):
            amount = 340_000
            refusals = [
                Refusal(
                    item="Full claim",
                    amount=amount,
                    insurer_reason="Non-disclosure and delayed intimation",
                    verdict="WRONGFUL",
                    rule_ids=["R01", "R02", "R05"],
                    why_simple_en="The insurer gives no clause.",
                    why_simple_hi="बीमाकर्ता ने कोई क्लॉज़ नहीं दिया।",
                    evidence_quote="as per policy terms and conditions",
                )
            ]
        else:
            refusals = [
                Refusal(
                    item="Diagnostics",
                    amount=150,
                    insurer_reason="Proportionate deduction",
                    verdict="WRONGFUL",
                    rule_ids=["R06"],
                    why_simple_en="Diagnostics cannot be reduced this way.",
                    why_simple_hi="जांच में इस तरह कटौती नहीं हो सकती।",
                    evidence_quote="proportionate deduction",
                )
            ]
        verdict = Verdict(
            policyholder_name="Demo Person",
            insurer="Example insurer",
            policy_number="P-1",
            claim_type="reimbursement",
            amount_claimed=1000,
            amount_paid=500,
            amount_refused=500,
            refusals=refusals,
            claim_submitted_date="2026-09-01",
            decision_date="2026-09-20",
        )
        return verdict, "gemini-3.6-flash"

    def generate_letters(self, case):
        self.letter_calls += 1
        return (
            Letters(
                grievance_letter="Dear insurer, please review.",
                ombudsman_complaint=(
                    "Complainant name and address: Demo Person, "
                    "[Please add your postal address]\n"
                    "Insurer branch: [Please add branch]\nFacts: The claim was refused.\n"
                    "Documents: Policy and letter.\nNature and extent of loss: ₹500.\n"
                    "Relief sought: Reconsider the claim."
                ),
            ),
            "gemini-3.6-flash",
        )

    def transcribe(self, data, mime_type):
        raise NotImplementedError


def test_api_upload_letters_status_and_demo(tmp_path):
    gemini = MockGemini()
    cache_dir = tmp_path / "demo_cache"
    app = create_app(SqliteCaseStore(tmp_path / "cases.db"), gemini, cache_dir)
    client = TestClient(app)

    created = client.post(
        "/api/cases",
        files=[("files[]", ("bill.png", b"not-an-image", "image/png"))],
        data={"notes": "A test note", "lang": "en"},
    )
    assert created.status_code == 200, created.text
    case = created.json()
    assert case["case_strength"] == "MEDIUM"
    assert case["model_used"] == "gemini-3.6-flash"
    assert gemini.analysis_calls == 1

    letters = client.post(f"/api/cases/{case['id']}/letters")
    assert letters.status_code == 200, letters.text
    assert "Complainant name and address" in letters.json()["ombudsman_complaint"]
    assert letters.json()["model_used"] == "gemini-3.6-flash"
    assert gemini.letter_calls == 1

    patched = client.patch(
        f"/api/cases/{case['id']}/status",
        json={"event": "grievance_sent", "date": "2026-11-02"},
    )
    assert patched.status_code == 200
    assert patched.json()["tracker_events"][0]["event"] == "grievance_sent"
    saved_case = client.get(f"/api/cases/{case['id']}")
    assert saved_case.status_code == 200
    assert saved_case.json()["letters_model_used"] == "gemini-3.6-flash"

    demo = client.post("/api/demo/ped-rejection")
    assert demo.status_code == 200, demo.text
    assert demo.json()["source"] == "demo:ped-rejection"
    cache = json.loads((cache_dir / "ped-rejection.json").read_text(encoding="utf-8"))
    assert cache["model_used"] == "gemini-3.6-flash"
    assert cache["cached_at"]
    assert cache["policyholder_name"] == "Demo Person"
    assert gemini.analysis_calls == 2
    assert client.get("/healthz").json() == {"status": "ok"}


class FailingGemini(MockGemini):
    def analyze(self, documents, notes=""):
        raise RuntimeError("all configured models unavailable")


def test_demo_uses_live_result_cache_but_upload_does_not(tmp_path):
    cached_at = "2026-11-11T12:30:00+00:00"
    seed = MockGemini()
    verdict, _ = seed.analyze([], "")
    cache_dir = tmp_path / "demo_cache"
    cache_dir.mkdir()
    cached_payload = {
        **verdict.model_dump(),
        "model_used": "gemini-3.6-flash",
        "cached_at": cached_at,
    }
    (cache_dir / "partial-cut.json").write_text(
        json.dumps(cached_payload, ensure_ascii=False), encoding="utf-8"
    )
    app = create_app(
        SqliteCaseStore(tmp_path / "fallback.db"),
        FailingGemini(),
        cache_dir,
    )
    client = TestClient(app)

    demo = client.post("/api/demo/partial-cut")
    assert demo.status_code == 200, demo.text
    assert demo.json()["cached"] is True
    assert demo.json()["cached_at"] == cached_at
    assert demo.json()["model_used"] == "gemini-3.6-flash"

    upload = client.post(
        "/api/cases",
        files=[("files[]", ("bill.png", b"not-an-image", "image/png"))],
        data={"lang": "en"},
    )
    assert upload.status_code == 502
