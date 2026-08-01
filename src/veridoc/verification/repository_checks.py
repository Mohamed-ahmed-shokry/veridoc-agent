"""Deterministic checks that compare invoices with persisted reference data."""

from __future__ import annotations

from veridoc.extraction.models import InvoiceExtraction
from veridoc.persistence.protocol import InvoiceRepository
from veridoc.verification.models import VerificationFinding
from veridoc.verification.vendors import vendor_key_for


def check_duplicate_invoice_number(
    invoice: InvoiceExtraction, repository: InvoiceRepository
) -> list[VerificationFinding]:
    """Return a finding when the vendor has already used this invoice number."""
    vendor_key = vendor_key_for(invoice)
    if vendor_key is None or invoice.invoice_number is None:
        return []
    existing_invoice = repository.find_invoice(vendor_key, invoice.invoice_number)
    if existing_invoice is None:
        return []
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
                "existing_invoice_date": (
                    existing_invoice.invoice_date.isoformat()
                    if existing_invoice.invoice_date is not None
                    else None
                ),
            },
        )
    ]
