"""Deterministic checks that compare invoices with persisted reference data."""

from __future__ import annotations

from collections.abc import Sequence

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationFinding
from veridoc.verification.references import HistoricalInvoice
from veridoc.verification.vendors import normalize_invoice_number, vendor_key_for


def check_duplicate_invoice_number(
    invoice: InvoiceExtraction, history: Sequence[HistoricalInvoice]
) -> list[VerificationFinding]:
    """Return a finding when the vendor history holds this invoice identity."""
    vendor_key = vendor_key_for(invoice)
    canonical_number = normalize_invoice_number(invoice.invoice_number)
    if vendor_key is None or canonical_number is None:
        return []
    for existing in history:
        if normalize_invoice_number(existing.invoice_number) != canonical_number:
            continue
        return [
            VerificationFinding(
                finding_type="duplicate_invoice_number",
                severity="high",
                explanation="This vendor already has an invoice with the extracted invoice number.",
                comparison_source="invoice_register",
                deterministic_rule="invoice_number must be unique within a vendor history",
                observed_value=invoice.invoice_number,
                expected_value="no existing invoice with this number",
                details={
                    "vendor_key": vendor_key,
                    "existing_invoice_number": existing.invoice_number,
                    "existing_invoice_date": (
                        existing.invoice_date.isoformat()
                        if existing.invoice_date is not None
                        else None
                    ),
                },
            )
        ]
    return []
