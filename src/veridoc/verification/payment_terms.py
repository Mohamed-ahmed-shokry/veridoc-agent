"""Pure deterministic payment terms and due date consistency verification."""

from __future__ import annotations

import re
from datetime import timedelta
from typing import Final

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationFinding

# Regex for "Net <N>", "<N> net", "<N> days net", "N/<N>", etc.
_NET_DAYS_RE: Final[re.Pattern[str]] = re.compile(
    r"^(?:net\s*(\d{1,3})|\b(\d{1,3})\s*(?:days?\s+net|net(?:\s+days?)?)|n/(\d{1,3}))\b",
    re.IGNORECASE,
)

# Regex for cash discount terms like "2/10 Net 30", "1/10, net 30", "2% 10 Net 30"
_CASH_DISCOUNT_NET_RE: Final[re.Pattern[str]] = re.compile(
    r"^\d+(?:\.\d+)?%?\s*(?:/|\s+)\s*\d+\s*,?\s*net\s*(\d{1,3})\b",
    re.IGNORECASE,
)

# Set of standard immediate payment terms
_IMMEDIATE_TERMS: Final[frozenset[str]] = frozenset(
    {
        "due on receipt",
        "due upon receipt",
        "payable on receipt",
        "payment on receipt",
        "immediate",
        "immediately",
        "cash on delivery",
        "cod",
        "due immediately",
        "net 0",
        "net 0 days",
    }
)


def parse_payment_terms_days(terms: str | None) -> int | None:
    """Extract contractual credit window days from standard commercial payment terms.

    Returns the integer number of days, or None if the terms are absent or
    cannot be deterministically parsed.
    """
    if terms is None:
        return None

    cleaned = " ".join(terms.strip().split())
    if not cleaned:
        return None

    lowered = cleaned.lower()
    if lowered in _IMMEDIATE_TERMS:
        return 0

    cash_match = _CASH_DISCOUNT_NET_RE.match(cleaned)
    if cash_match is not None:
        return int(cash_match.group(1))

    net_match = _NET_DAYS_RE.search(cleaned)
    if net_match is not None:
        for group in net_match.groups():
            if group is not None:
                return int(group)

    return None


def check_payment_terms_due_date(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Flag invoices whose due date conflicts with stated payment terms and issue date.

    Returns findings when:
    - `due_date < expected_due_date` (accelerated due date, severity="high");
    - `due_date > expected_due_date` beyond any weekend business-day adjustment
      (extended due date, severity="medium").

    Returns [] when fields are missing, terms cannot be deterministically parsed,
    or the due date matches or incorporates a valid weekend roll to Monday.
    """
    invoice_date = invoice.invoice_date
    due_date = invoice.due_date
    payment_terms = invoice.payment_terms

    if invoice_date is None or due_date is None or payment_terms is None:
        return []

    terms_days = parse_payment_terms_days(payment_terms)
    if terms_days is None:
        return []

    expected_due_date = invoice_date + timedelta(days=terms_days)
    if due_date == expected_due_date:
        return []

    # Check for standard commercial weekend roll to the next business day (Monday):
    # If expected_due_date is Saturday (weekday == 5) and due_date is Monday (+2 days)
    # If expected_due_date is Sunday (weekday == 6) and due_date is Monday (+1 day)
    expected_weekday = expected_due_date.weekday()
    if expected_weekday == 5 and due_date == expected_due_date + timedelta(days=2):
        return []
    if expected_weekday == 6 and due_date == expected_due_date + timedelta(days=1):
        return []

    discrepancy_days = (due_date - expected_due_date).days
    is_accelerated = discrepancy_days < 0

    if is_accelerated:
        abs_days = abs(discrepancy_days)
        suffix = "day" if abs_days == 1 else "days"
        explanation = (
            f"The invoice due date ({due_date.isoformat()}) is {abs_days} {suffix} "
            f"earlier than the {terms_days}-day payment terms specify "
            f"(expected {expected_due_date.isoformat()})."
            if terms_days > 0
            else (
                f"The invoice specifies immediate terms ('{payment_terms}'), but due date "
                f"({due_date.isoformat()}) is earlier than invoice date ({invoice_date.isoformat()})."
            )
        )
        severity = "high"
    else:
        suffix = "day" if discrepancy_days == 1 else "days"
        explanation = (
            f"The invoice due date ({due_date.isoformat()}) is {discrepancy_days} {suffix} "
            f"later than the {terms_days}-day payment terms specify "
            f"(expected {expected_due_date.isoformat()})."
            if terms_days > 0
            else (
                f"The invoice specifies immediate payment ('{payment_terms}'), but due date "
                f"({due_date.isoformat()}) is {discrepancy_days} {suffix} after invoice date "
                f"({invoice_date.isoformat()})."
            )
        )
        severity = "medium"

    return [
        VerificationFinding(
            finding_type="payment_terms_due_date_mismatch",
            severity=severity,
            explanation=explanation,
            comparison_source="invoice_fields",
            deterministic_rule="invoice.due_date == invoice.invoice_date + payment_terms_days",
            observed_value=due_date.isoformat(),
            expected_value=expected_due_date.isoformat(),
            details={
                "payment_terms": payment_terms,
                "terms_days": terms_days,
                "expected_due_date": expected_due_date.isoformat(),
                "observed_due_date": due_date.isoformat(),
                "discrepancy_days": discrepancy_days,
                "is_accelerated": is_accelerated,
            },
        )
    ]
