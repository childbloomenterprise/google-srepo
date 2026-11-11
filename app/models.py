from datetime import date, datetime
from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator


class Refusal(BaseModel):
    item: str
    amount: float
    insurer_reason: str
    verdict: Literal["WRONGFUL", "QUESTIONABLE", "VALID"]
    rule_ids: list[str] = Field(default_factory=list)
    why_simple_en: str
    why_simple_hi: str
    evidence_quote: str


class Verdict(BaseModel):
    policyholder_name: str | None = None
    insurer: str | None = None
    policy_number: str | None = None
    hospital: str | None = None
    policy_first_start_date: str | None = None
    admission_date: str | None = None
    discharge_date: str | None = None
    decision_date: str | None = None
    claim_submitted_date: str | None = None
    continuous_cover_months: int | None = None
    claim_type: Literal["cashless", "reimbursement", "unknown"] = "unknown"
    amount_claimed: float | None = None
    amount_paid: float | None = None
    amount_refused: float | None = None
    refusals: list[Refusal] = Field(default_factory=list)
    missing_info: list[str] = Field(default_factory=list)

    @field_validator(
        "policy_first_start_date",
        "admission_date",
        "discharge_date",
        "decision_date",
        "claim_submitted_date",
        mode="before",
    )
    @classmethod
    def validate_iso_date(cls, value: Any) -> str | None:
        if value is None or value == "":
            return None
        if not isinstance(value, str):
            raise ValueError("Dates must use YYYY-MM-DD format")
        try:
            return date.fromisoformat(value).isoformat()
        except ValueError:
            formats = (
                "%d %B %Y",
                "%d %b %Y",
                "%B %d, %Y",
                "%b %d, %Y",
                "%d/%m/%Y",
                "%d-%m-%Y",
                "%Y/%m/%d",
            )
            for date_format in formats:
                try:
                    return datetime.strptime(value, date_format).date().isoformat()
                except ValueError:
                    continue
        raise ValueError("Dates must use YYYY-MM-DD format")


class Letters(BaseModel):
    grievance_letter: str
    ombudsman_complaint: str


class VoiceFacts(BaseModel):
    insurer: str | None = None
    policy_number: str | None = None
    hospital: str | None = None
    admission_date: str | None = None
    amount_claimed: float | None = None
    amount_paid: float | None = None
    rejection_reason: str | None = None
    continuous_cover_months: int | None = None


class VoiceResult(BaseModel):
    transcript: str
    facts: VoiceFacts
