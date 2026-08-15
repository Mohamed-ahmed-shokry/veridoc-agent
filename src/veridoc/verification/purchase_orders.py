"""Deterministic invoice and purchase-order reconciliation checks."""

from __future__ import annotations

from veridoc.extraction.models import InvoiceExtraction
from veridoc.persistence.protocol import InvoiceRepository
from veridoc.verification.line_items import line_item_key
from veridoc.verification.models import VerificationFinding
from veridoc.verification.references import ReferenceLineItem
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
    findings.extend(_check_line_items(invoice, purchase_order.line_items))
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


def _check_line_items(
    invoice: InvoiceExtraction, purchase_order_line_items: list[ReferenceLineItem]
) -> list[VerificationFinding]:
    findings: list[VerificationFinding] = []
    remaining_purchase_order_line_items = list(purchase_order_line_items)
    for index, invoice_line_item in enumerate(invoice.line_items):
        key = line_item_key(
            invoice_line_item.product_identifier, invoice_line_item.description
        )
        if key is None:
            continue
        matching_index = next(
            (
                candidate_index
                for candidate_index, purchase_order_line_item in enumerate(
                    remaining_purchase_order_line_items
                )
                if line_item_key(
                    purchase_order_line_item.product_identifier,
                    purchase_order_line_item.description,
                )
                == key
            ),
            None,
        )
        if matching_index is None:
            findings.append(
                VerificationFinding(
                    finding_type="purchase_order_mismatch",
                    severity="high",
                    explanation="The invoice line item does not appear on the referenced purchase order.",
                    comparison_source="purchase_order",
                    deterministic_rule="invoice line item must exist on purchase order",
                    observed_value=key,
                    expected_value="matching purchase-order line item",
                    details={"field": "line_item", "line_item_index": index},
                )
            )
            continue
        matching_purchase_order_line_item = remaining_purchase_order_line_items.pop(
            matching_index
        )
        for field in ("quantity", "unit_price", "total_price"):
            observed_value = getattr(invoice_line_item, field)
            expected_value = getattr(matching_purchase_order_line_item, field)
            if observed_value is None or expected_value is None:
                continue
            if observed_value == expected_value:
                continue
            findings.append(
                VerificationFinding(
                    finding_type="purchase_order_mismatch",
                    severity="high",
                    explanation=f"The invoice line-item {field} does not match the purchase order.",
                    comparison_source="purchase_order",
                    deterministic_rule=f"invoice.line_item.{field} == purchase_order.line_item.{field}",
                    observed_value=str(observed_value),
                    expected_value=str(expected_value),
                    details={"field": f"line_item_{field}", "line_item_index": index},
                )
            )
    return findings
