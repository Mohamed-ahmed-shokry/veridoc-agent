"""Deterministic excessive credit window and due date bound verification.

In commercial accounts payable (AP) operations, the contractual credit window
between invoice issue date (invoice_date) and payable due date (due_date) is
governed by standard trade credit conventions. Typical credit terms range from
immediate payment (Net 0) up to standard quarterly or semi-annual windows (Net 30,
Net 60, Net 90, Net 120, Net 180, Net 360).

While Phase 28 checks consistency against explicit contractual terms (e.g. Net 30),
many invoices omit explicit payment terms or use free-form phrasing. When vision/OCR
models hallucinate years (e.g. misreading 2026 as 2036), confuse due dates with
multi-year contract expirations or equipment warranty dates, or extract dates
years into the future, the invoice could bypass date verification if
invoice_date <= due_date.

Establishing an absolute bound (MAXIMUM_CREDIT_WINDOW_DAYS = 365) ensures that
any invoice carrying an abnormal multi-year credit window is routed to review.
"""

from __future__ import annotations

from datetime import timedelta
from typing import Final

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationFinding

MAXIMUM_CREDIT_WINDOW_DAYS: Final[int] = 365


def check_excessive_due_date_window(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Flag invoices whose payable due date exceeds the maximum credit window.

    Returns an empty list when:
    - invoice_date is None or due_date is None;
    - due_date < invoice_date (inverted dates are checked by arithmetic rules);
    - (due_date - invoice_date).days <= MAXIMUM_CREDIT_WINDOW_DAYS (365 days).

    Returns a list with one ``excessive_due_date_window`` finding (severity="medium")
    when (due_date - invoice_date).days > MAXIMUM_CREDIT_WINDOW_DAYS.
    """
    invoice_date = invoice.invoice_date
    due_date = invoice.due_date

    if invoice_date is None or due_date is None:
        return []

    if due_date < invoice_date:
        return []

    credit_window_days = (due_date - invoice_date).days
    if credit_window_days <= MAXIMUM_CREDIT_WINDOW_DAYS:
        return []

    max_allowed_due_date = invoice_date + timedelta(days=MAXIMUM_CREDIT_WINDOW_DAYS)
    return [
        VerificationFinding(
            finding_type="excessive_due_date_window",
            severity="medium",
            explanation=(
                f"The invoice due date ({due_date.isoformat()}) is {credit_window_days} days "
                f"after the invoice date ({invoice_date.isoformat()}), exceeding the maximum "
                f"commercial credit window of {MAXIMUM_CREDIT_WINDOW_DAYS} days "
                f"(expected on or before {max_allowed_due_date.isoformat()}). "
                "Excessive credit windows may indicate OCR year hallucination, warranty date "
                "misextraction, or fictitious deferred liability."
            ),
            comparison_source="invoice_fields",
            deterministic_rule=f"due_date - invoice_date <= {MAXIMUM_CREDIT_WINDOW_DAYS} days",
            observed_value=due_date.isoformat(),
            expected_value=max_allowed_due_date.isoformat(),
            details={
                "credit_window_days": credit_window_days,
                "max_allowed_days": MAXIMUM_CREDIT_WINDOW_DAYS,
                "invoice_date": invoice_date.isoformat(),
                "due_date": due_date.isoformat(),
            },
        )
    ]
