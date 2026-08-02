"""Pure deterministic arithmetic checks for extracted invoices."""

from __future__ import annotations

from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationFinding


def check_arithmetic(invoice: InvoiceExtraction) -> list[VerificationFinding]:
    """Return findings for internally inconsistent invoice facts."""
    findings = _check_invoice_total(invoice)
    findings.extend(_check_line_item_amounts(invoice))
    findings.extend(_check_line_items_subtotal(invoice))
    findings.extend(_check_invoice_dates(invoice))
    return findings


def _check_invoice_total(invoice: InvoiceExtraction) -> list[VerificationFinding]:
    subtotal = invoice.subtotal
    tax = invoice.tax
    discount = invoice.discount
    total = invoice.total
    if subtotal is None or tax is None or discount is None or total is None:
        return []

    expected_total = subtotal + tax - discount
    if total == expected_total:
        return []
    return [
        VerificationFinding(
            finding_type="invoice_total_mismatch",
            severity="high",
            explanation="The invoice total does not equal subtotal plus tax minus discount.",
            comparison_source="invoice_fields",
            deterministic_rule="subtotal + tax - discount == total",
            observed_value=str(total),
            expected_value=str(expected_total),
            details={"currency": invoice.currency},
        )
    ]


def _check_line_item_amounts(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    findings: list[VerificationFinding] = []
    for index, line_item in enumerate(invoice.line_items):
        quantity = line_item.quantity
        unit_price = line_item.unit_price
        total_price = line_item.total_price
        if quantity is None or unit_price is None or total_price is None:
            continue
        expected_total = quantity * unit_price
        if total_price != expected_total:
            findings.append(
                VerificationFinding(
                    finding_type="line_item_amount_mismatch",
                    severity="high",
                    explanation="A line-item total does not equal quantity multiplied by unit price.",
                    comparison_source="invoice_line_items",
                    deterministic_rule="quantity * unit_price == total_price",
                    observed_value=str(total_price),
                    expected_value=str(expected_total),
                    details={
                        "line_item_index": index,
                        "product_identifier": line_item.product_identifier,
                    },
                )
            )
    return findings


def _check_line_items_subtotal(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    if invoice.subtotal is None or not invoice.line_items:
        return []
    expected_subtotal = Decimal(0)
    for line_item in invoice.line_items:
        if line_item.total_price is None:
            return []
        expected_subtotal += line_item.total_price
    if invoice.subtotal == expected_subtotal:
        return []
    return [
        VerificationFinding(
            finding_type="line_items_subtotal_mismatch",
            severity="high",
            explanation="The sum of line-item totals does not equal the invoice subtotal.",
            comparison_source="invoice_line_items",
            deterministic_rule="sum(line_item.total_price) == subtotal",
            observed_value=str(invoice.subtotal),
            expected_value=str(expected_subtotal),
            details={"line_item_count": len(invoice.line_items)},
        )
    ]


def _check_invoice_dates(invoice: InvoiceExtraction) -> list[VerificationFinding]:
    if invoice.invoice_date is None or invoice.due_date is None:
        return []
    if invoice.invoice_date <= invoice.due_date:
        return []
    return [
        VerificationFinding(
            finding_type="invoice_date_after_due_date",
            severity="medium",
            explanation="The invoice date occurs after its due date.",
            comparison_source="invoice_fields",
            deterministic_rule="invoice_date <= due_date",
            observed_value=invoice.invoice_date.isoformat(),
            expected_value=invoice.due_date.isoformat(),
        )
    ]
