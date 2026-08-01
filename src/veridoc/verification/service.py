"""API-neutral composition of Phase 3 verification checks."""

from __future__ import annotations

from veridoc.extraction.models import InvoiceExtraction
from veridoc.persistence.protocol import InvoiceRepository
from veridoc.verification.arithmetic import check_arithmetic
from veridoc.verification.field_history import check_payment_terms
from veridoc.verification.history import check_historical_total
from veridoc.verification.line_items import (
    check_line_item_occurrence,
    check_line_item_statistics,
)
from veridoc.verification.models import VerificationFinding, VerificationResult
from veridoc.verification.purchase_orders import check_purchase_order
from veridoc.verification.repository_checks import check_duplicate_invoice_number
from veridoc.verification.vendors import vendor_key_for


class VerificationService:
    """Run deterministic verification without coupling to a delivery boundary."""

    def __init__(self, repository: InvoiceRepository) -> None:
        self._repository = repository

    def verify(self, invoice: InvoiceExtraction) -> VerificationResult:
        """Return all applicable deterministic findings for one invoice."""
        findings = check_arithmetic(invoice)
        findings.extend(check_duplicate_invoice_number(invoice, self._repository))
        findings.extend(check_purchase_order(invoice, self._repository))

        vendor_key = vendor_key_for(invoice)
        if vendor_key is None:
            findings.extend(_missing_vendor_history_finding(invoice))
            return VerificationResult(findings=findings)

        history = self._repository.list_vendor_invoices(vendor_key)
        findings.extend(check_historical_total(invoice, history))
        findings.extend(check_line_item_occurrence(invoice, history))
        findings.extend(check_line_item_statistics(invoice, history))
        findings.extend(check_payment_terms(invoice, history))
        return VerificationResult(findings=findings)


def _missing_vendor_history_finding(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    if (
        invoice.total is None
        and not invoice.line_items
        and invoice.payment_terms is None
    ):
        return []
    return [
        VerificationFinding(
            finding_type="insufficient_history",
            severity="info",
            explanation="Vendor identity is absent, so vendor-history comparisons cannot run.",
            comparison_source="vendor_history",
            deterministic_rule="vendor_identifier or vendor_name is required",
            details={"metric": "vendor_history"},
        )
    ]
