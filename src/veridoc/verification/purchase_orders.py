"""Deterministic invoice and purchase-order reconciliation checks."""

from __future__ import annotations

from veridoc.extraction.models import InvoiceExtraction
from veridoc.persistence.protocol import InvoiceRepository
from veridoc.verification.models import VerificationFinding
from veridoc.verification.vendors import vendor_key_for


def check_purchase_order(
    invoice: InvoiceExtraction, repository: InvoiceRepository
) -> list[VerificationFinding]:
    """Compare extracted invoice facts with their referenced purchase order."""
    vendor_key = vendor_key_for(invoice)
    if vendor_key is None or invoice.purchase_order_number is None:
        return []
    purchase_order = repository.get_purchase_order(
        vendor_key, invoice.purchase_order_number
    )
    if purchase_order is None:
        return [
            VerificationFinding(
                finding_type="purchase_order_mismatch",
                severity="high",
                explanation="No matching purchase order was found for the extracted PO number.",
                comparison_source="purchase_order",
                deterministic_rule="referenced purchase order must exist for the vendor",
                observed_value=invoice.purchase_order_number,
                expected_value="matching purchase order",
                details={"vendor_key": vendor_key},
            )
        ]

    findings: list[VerificationFinding] = []
    if invoice.currency is not None and purchase_order.currency is not None:
        findings.extend(
            _mismatch_finding(
                field="currency",
                observed_value=invoice.currency,
                expected_value=purchase_order.currency,
            )
        )
    if invoice.total is not None and purchase_order.total is not None:
        findings.extend(
            _mismatch_finding(
                field="total",
                observed_value=str(invoice.total),
                expected_value=str(purchase_order.total),
            )
        )
    return findings


def _mismatch_finding(
    *, field: str, observed_value: str, expected_value: str
) -> list[VerificationFinding]:
    if observed_value == expected_value:
        return []
    return [
        VerificationFinding(
            finding_type="purchase_order_mismatch",
            severity="high",
            explanation=f"The invoice {field} does not match the referenced purchase order.",
            comparison_source="purchase_order",
            deterministic_rule=f"invoice.{field} == purchase_order.{field}",
            observed_value=observed_value,
            expected_value=expected_value,
            details={"field": field},
        )
    ]
