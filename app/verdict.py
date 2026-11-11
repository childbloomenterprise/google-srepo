from datetime import date, datetime, timedelta
from typing import Any

from app.models import Verdict
from app.rules import rule_ids


def format_indian_number(amount: float | int) -> str:
    rounded = int(round(amount))
    sign = "-" if rounded < 0 else ""
    digits = str(abs(rounded))
    if len(digits) <= 3:
        return f"{sign}{digits}"
    tail = digits[-3:]
    head = digits[:-3]
    groups: list[str] = []
    while len(head) > 2:
        groups.insert(0, head[-2:])
        head = head[:-2]
    if head:
        groups.insert(0, head)
    return f"{sign}{','.join(groups)},{tail}"


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(value[:10])
    except ValueError:
        return None


def derive_verdict(verdict: Verdict | dict[str, Any], created_at: str) -> dict[str, Any]:
    parsed = verdict if isinstance(verdict, Verdict) else Verdict.model_validate(verdict)
    valid_ids = rule_ids()
    normalized_refusals: list[dict[str, Any]] = []
    for refusal in parsed.refusals:
        item = refusal.model_dump()
        item["rule_ids"] = [rule_id for rule_id in item["rule_ids"] if rule_id in valid_ids]
        if item["verdict"] == "WRONGFUL" and not item["rule_ids"]:
            item["verdict"] = "QUESTIONABLE"
        elif item["verdict"] == "QUESTIONABLE" and not item["rule_ids"]:
            item["verdict"] = "VALID"
        normalized_refusals.append(item)

    recoverable = sum(
        item["amount"] for item in normalized_refusals if item["verdict"] == "WRONGFUL"
    )
    possible = sum(
        item["amount"] for item in normalized_refusals if item["verdict"] == "QUESTIONABLE"
    )
    refused_total = (
        parsed.amount_refused
        if parsed.amount_refused is not None
        else sum(item["amount"] for item in normalized_refusals)
    )
    if refused_total > 0 and recoverable >= 0.5 * refused_total:
        strength = "STRONG"
    elif refused_total > 0 and (recoverable + possible) >= 0.3 * refused_total:
        strength = "MEDIUM"
    else:
        strength = "WEAK"

    formatted_recoverable = format_indian_number(recoverable)
    headline_en = f"₹{formatted_recoverable} wrongly cut — {strength.lower()} case"
    headline_hi = {
        "STRONG": f"₹{formatted_recoverable} गलत काटे गए — मजबूत मामला",
        "MEDIUM": f"₹{formatted_recoverable} गलत काटे गए — मध्यम मामला",
        "WEAK": f"₹{formatted_recoverable} गलत काटे गए — कमजोर मामला",
    }[strength]

    submitted = _parse_date(parsed.claim_submitted_date)
    decided = _parse_date(parsed.decision_date)
    days_to_decision = (decided - submitted).days if submitted and decided else None
    interest_due = (
        parsed.claim_type == "reimbursement"
        and days_to_decision is not None
        and days_to_decision > 15
    )

    try:
        created_day = datetime.fromisoformat(created_at.replace("Z", "+00:00")).date()
    except ValueError:
        created_day = date.fromisoformat(created_at[:10])
    events = [
        {
            "event": "grievance_due",
            "date": created_day.isoformat(),
            "label": "Grievance to insurer",
        },
        {
            "event": "reminder_due",
            "date": (created_day + timedelta(days=15)).isoformat(),
            "label": "Reminder",
        },
        {
            "event": "ombudsman_eligible",
            "date": (created_day + timedelta(days=31)).isoformat(),
            "label": "Insurance Ombudsman (if no or unsatisfactory reply)",
        },
    ]
    ombudsman_reply_deadline = None

    return {
        **parsed.model_dump(exclude={"refusals"}),
        "refusals": normalized_refusals,
        "recoverable_amount": round(recoverable, 2),
        "possible_amount": round(possible, 2),
        "refused_total": round(refused_total, 2),
        "case_strength": strength,
        "headline_en": headline_en,
        "headline_hi": headline_hi,
        "interest_due": interest_due,
        "interest_days_late": max(days_to_decision - 15, 0) if interest_due else 0,
        "interest_rule_id": "R07" if interest_due else None,
        "ombudsman_eligible": refused_total <= 5_000_000,
        "timeline": events,
        "ombudsman_reply_deadline": ombudsman_reply_deadline,
    }
