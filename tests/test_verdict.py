import pytest

from app.models import Verdict
from app.verdict import derive_verdict, format_indian_number

CREATED_AT = "2026-11-01T10:00:00+00:00"


def base_verdict(**overrides):
    values = {
        "policyholder_name": "Test Person",
        "insurer": "Example insurer",
        "policy_number": "P-1",
        "claim_type": "unknown",
        "amount_claimed": 1000,
        "amount_paid": 500,
        "amount_refused": 500,
        "refusals": [],
    }
    values.update(overrides)
    return Verdict.model_validate(values)


def refusal(verdict="WRONGFUL", rule_ids=None, amount=300):
    return {
        "item": "Diagnostics",
        "amount": amount,
        "insurer_reason": "Room proportion",
        "verdict": verdict,
        "rule_ids": rule_ids or ["R06"],
        "why_simple_en": "This deduction is not allowed.",
        "why_simple_hi": "यह कटौती मान्य नहीं है।",
        "evidence_quote": "proportionate deduction",
    }


def test_invalid_rule_id_is_removed_and_wrongful_downgraded():
    result = derive_verdict(base_verdict(refusals=[refusal(rule_ids=["R99"])]), CREATED_AT)
    assert result["refusals"][0]["rule_ids"] == []
    assert result["refusals"][0]["verdict"] == "QUESTIONABLE"


def test_questionable_without_valid_rule_becomes_valid():
    result = derive_verdict(
        base_verdict(refusals=[refusal(verdict="QUESTIONABLE", rule_ids=["R99"])]), CREATED_AT
    )
    assert result["refusals"][0]["verdict"] == "VALID"


def test_strength_thresholds_and_zero_refused_total():
    strong = derive_verdict(
        base_verdict(refusals=[refusal(amount=250)], amount_refused=500), CREATED_AT
    )
    medium = derive_verdict(
        base_verdict(refusals=[refusal(amount=150, verdict="QUESTIONABLE")], amount_refused=500),
        CREATED_AT,
    )
    weak = derive_verdict(
        base_verdict(refusals=[refusal(amount=100, verdict="VALID")], amount_refused=500), CREATED_AT
    )
    zero = derive_verdict(base_verdict(amount_refused=0, refusals=[]), CREATED_AT)
    assert strong["case_strength"] == "STRONG"
    assert medium["case_strength"] == "MEDIUM"
    assert weak["case_strength"] == "WEAK"
    assert zero["case_strength"] == "WEAK"


def test_interest_flag_is_false_at_15_days_and_true_at_16():
    shared = {
        "claim_type": "reimbursement",
        "claim_submitted_date": "2026-09-01",
        "refusals": [],
    }
    at_15 = derive_verdict(
        base_verdict(**shared, decision_date="2026-09-16"), CREATED_AT
    )
    at_16 = derive_verdict(
        base_verdict(**shared, decision_date="2026-09-17"), CREATED_AT
    )
    assert at_15["interest_due"] is False
    assert at_16["interest_due"] is True
    assert at_16["interest_days_late"] == 1
    assert at_16["interest_rule_id"] == "R07"


def test_indian_number_formatting_and_ombudsman_cap():
    assert format_indian_number(142300) == "1,42,300"
    eligible = derive_verdict(base_verdict(amount_refused=5_000_000), CREATED_AT)
    over_cap = derive_verdict(base_verdict(amount_refused=5_000_001), CREATED_AT)
    assert eligible["ombudsman_eligible"] is True
    assert over_cap["ombudsman_eligible"] is False


def test_dates_are_optional_but_present_dates_must_be_iso_formatted():
    assert Verdict.model_validate(
        {"policyholder_name": None, "insurer": None, "policy_number": None}
    ).admission_date is None
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        base_verdict(admission_date="20/08/2026")
