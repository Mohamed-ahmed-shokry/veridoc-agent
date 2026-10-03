"""Deterministic future invoice date check.

An invoice whose issue date occurs in the future relative to the current
processing date is a critical indicator of financial accounting cutoff
evasion, premature billing or revenue recognition fraud, or vision/OCR date
extraction errors (such as year hallucination or month-day transposition).
Under GAAP, IFRS, and tax statutory frameworks (VAT, GST, sales tax),
post-dated invoices cannot legally be posted or claimed for input deductions
before their tax point / issue date occurs.
"""

from __future__ import annotations

from datetime import UTC, date, datetime

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationFinding


def check_future_invoice_date(
    invoice: InvoiceExtraction,
    reference_date: date | None = None,
) -> list[VerificationFinding]:
    """Return a finding when the invoice issue date lies in the future.

    Args:
        invoice: The structured invoice extraction to check.
        reference_date: The date to compare against. Defaults to today (UTC).
            Pass an explicit value in tests to avoid time-dependent results.

    Returns:
        A list containing one ``future_invoice_date`` finding if the invoice
        date is strictly after the reference date, or an empty list otherwise.
    """
    if invoice.invoice_date is None:
        return []

    today = reference_date if reference_date is not None else datetime.now(UTC).date()
    if invoice.invoice_date <= today:
        return []

    days_in_future = (invoice.invoice_date - today).days
    day_label = "day" if days_in_future == 1 else "days"
    return [
        VerificationFinding(
            finding_type="future_invoice_date",
            severity="medium",
            explanation=(
                f"The invoice date is {days_in_future} {day_label} in the future "
                "relative to the processing date. Post-dated invoices may indicate "
                "forward-dating fraud, accounting cutoff evasion, or date "
                "extraction errors."
            ),
            comparison_source="invoice_fields",
            deterministic_rule="invoice_date <= today",
            observed_value=invoice.invoice_date.isoformat(),
            expected_value=today.isoformat(),
            details={
                "days_in_future": days_in_future,
                "reference_date": today.isoformat(),
            },
        )
    ]
