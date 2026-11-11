from types import SimpleNamespace

import app.gemini_service as gemini_module
from app.gemini_service import GeminiService
from app.models import Verdict


class ApiFailure(Exception):
    def __init__(self, code):
        super().__init__(f"{code} API failure")
        self.code = code


class FakeModels:
    def __init__(self, generate):
        self.generate = generate
        self.calls = []

    def generate_content(self, *, model, contents, config):
        self.calls.append(model)
        return self.generate(model)


class FakeClient:
    def __init__(self, models):
        self.models = models


def run_chain(service):
    return service._generate(
        contents=["test"],
        schema=Verdict,
        system_instruction="test",
        chain_env="CB_MODEL_CHAIN_ANALYSIS",
        default_chain="first,second",
        legacy_env="CB_MODEL_ANALYSIS",
    )


def test_429_moves_to_next_model_without_retry_and_quarantines_first(monkeypatch):
    quarantined = {}
    monkeypatch.setattr(gemini_module, "_QUARANTINED_MODELS", quarantined)
    monkeypatch.setenv("CB_MODEL_CHAIN_ANALYSIS", "first,second")
    monkeypatch.delenv("CB_MODEL_ANALYSIS", raising=False)
    monkeypatch.setattr(
        gemini_module.time,
        "sleep",
        lambda _: (_ for _ in ()).throw(AssertionError("429 must not retry")),
    )
    models = FakeModels(
        lambda model: (_ for _ in ()).throw(ApiFailure(429)) if model == "first" else "ok"
    )

    response, model_used = run_chain(GeminiService(FakeClient(models)))

    assert response == "ok"
    assert model_used == "second"
    assert models.calls == ["first", "second"]
    assert quarantined["first"] > gemini_module.time.monotonic()


def test_503_retries_once_then_moves_to_next_model(monkeypatch):
    monkeypatch.setattr(gemini_module, "_QUARANTINED_MODELS", {})
    monkeypatch.setenv("CB_MODEL_CHAIN_ANALYSIS", "first,second")
    monkeypatch.delenv("CB_MODEL_ANALYSIS", raising=False)
    sleeps = []
    monkeypatch.setattr(gemini_module.time, "sleep", sleeps.append)
    models = FakeModels(
        lambda model: (
            (_ for _ in ()).throw(ApiFailure(503)) if model == "first" else "ok"
        )
    )

    response, model_used = run_chain(GeminiService(FakeClient(models)))

    assert response == "ok"
    assert model_used == "second"
    assert models.calls == ["first", "first", "second"]
    assert sleeps == [2]


def test_quarantined_model_is_skipped_until_ttl_expires(monkeypatch):
    monkeypatch.setenv("CB_MODEL_CHAIN_ANALYSIS", "first,second")
    monkeypatch.delenv("CB_MODEL_ANALYSIS", raising=False)
    monkeypatch.setattr(
        gemini_module,
        "_QUARANTINED_MODELS",
        {"first": gemini_module.time.monotonic() + 30},
    )
    models = FakeModels(lambda _: "ok")

    response, model_used = run_chain(GeminiService(FakeClient(models)))

    assert response == "ok"
    assert model_used == "second"
    assert models.calls == ["second"]


def test_expired_quarantine_allows_model_to_be_tried(monkeypatch):
    quarantined = {"first": gemini_module.time.monotonic() - 1}
    monkeypatch.setattr(gemini_module, "_QUARANTINED_MODELS", quarantined)
    monkeypatch.setenv("CB_MODEL_CHAIN_ANALYSIS", "first,second")
    monkeypatch.delenv("CB_MODEL_ANALYSIS", raising=False)
    models = FakeModels(lambda _: "ok")

    response, model_used = run_chain(GeminiService(FakeClient(models)))

    assert response == "ok"
    assert model_used == "first"
    assert models.calls == ["first"]
    assert "first" not in quarantined


def test_analysis_returns_model_that_produced_verdict(monkeypatch):
    monkeypatch.setattr(gemini_module, "_QUARANTINED_MODELS", {})
    monkeypatch.setenv("CB_MODEL_CHAIN_ANALYSIS", "gemini-3.6-flash")
    monkeypatch.delenv("CB_MODEL_ANALYSIS", raising=False)
    verdict = Verdict(
        policyholder_name="Demo Person",
        insurer="Example insurer",
        policy_number="P-1",
        refusals=[],
    )
    models = FakeModels(lambda _: SimpleNamespace(parsed=verdict))

    result, model_used = GeminiService(FakeClient(models)).analyze([("bill.png", b"bytes")])

    assert result == verdict
    assert model_used == "gemini-3.6-flash"
    assert models.calls == ["gemini-3.6-flash"]


def test_legacy_model_setting_is_prepended_to_configured_chain(monkeypatch):
    monkeypatch.setenv("CB_MODEL_CHAIN_ANALYSIS", "configured,other")
    monkeypatch.setenv("CB_MODEL_ANALYSIS", "legacy")

    assert GeminiService._model_chain(
        "CB_MODEL_CHAIN_ANALYSIS", "default", "CB_MODEL_ANALYSIS"
    ) == ["legacy", "configured", "other"]


def test_status_code_falls_back_to_leading_digits():
    class PlainError(Exception):
        pass

    assert GeminiService._status_code(ApiFailure(404)) == 404
    assert GeminiService._status_code(PlainError("503 UNAVAILABLE: busy")) == 503
