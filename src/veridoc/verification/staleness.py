"""Deterministic staleness check for invoices with no purchase-order anchor.

An invoice issued more than STALENESS_THRESHOLD_DAYS before the current
processing date, with no purchase-order reference and a positive total,
is a meaningful indicator of backdating fraud or inadvertent resubmission.
Invoices anchored to a purchase order are excluded: long-running contracts
routinely produce invoices submitted well after the PO issuance date, and
those invoices already pass through the PO-ceiling check.  Zero- or
absent-total invoices are excluded because they carry no payment risk.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationFinding

STALENESS_THRESHOLD_DAYS = 90


def check_invoice_staleness(
    invoice: InvoiceExtraction,
    reference_date: date | None = None,
) -> list[VerificationFinding]:
    """Return a finding when the invoice date is stale with no PO reference.

    Args:
        invoice: The structured invoice extraction to check.
        reference_date: The date to compare against.  Defaults to today.
            Pass an explicit value in tests to avoid time-dependent results.

    Returns:
        A list containing one ``stale_invoice`` finding if all staleness
        conditions are met, or an empty list otherwise.
    """
    if invoice.invoice_date is None:
        return []
    if invoice.total is None or invoice.total <= Decimal(0):
        return []
    if invoice.purchase_order_number and invoice.purchase_order_number.strip():
        return []

    today = reference_date if reference_date is not None else date.today()
    threshold_date = today - timedelta(days=STALENESS_THRESHOLD_DAYS)
    if invoice.invoice_date >= threshold_date:
        return []

    days_old = (today - invoice.invoice_date).days
    return [
        VerificationFinding(
            finding_type="stale_invoice",
            severity="medium",
            explanation=(
                f"The invoice date is {days_old} days old with no purchase-order "
                "reference.  Invoices this old without a PO anchor may indicate "
                "backdating or resubmission."
            ),
            comparison_source="invoice_fields",
            deterministic_rule=(
                f"invoice_date < today - {STALENESS_THRESHOLD_DAYS} days "
                "and purchase_order_number is absent and total > 0"
            ),
            observed_value=invoice.invoice_date.isoformat(),
            expected_value=threshold_date.isoformat(),
            details={
                "days_old": days_old,
                "threshold_days": STALENESS_THRESHOLD_DAYS,
                "reference_date": today.isoformat(),
            },
        )
    ]
