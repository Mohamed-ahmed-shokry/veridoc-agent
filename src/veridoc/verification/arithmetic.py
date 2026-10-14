"""Pure deterministic arithmetic checks for extracted invoices."""

from __future__ import annotations

from decimal import Decimal
from typing import Final

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationFinding

DEFAULT_ROUNDING_TOLERANCE: Final[Decimal] = Decimal("0.02")


def check_arithmetic(
    invoice: InvoiceExtraction,
    rounding_tolerance: Decimal = DEFAULT_ROUNDING_TOLERANCE,
) -> list[VerificationFinding]:
    """Return findings for internally inconsistent invoice facts."""
    findings = check_invoice_total(invoice, rounding_tolerance=rounding_tolerance)
    findings.extend(
        check_line_item_amounts(invoice, rounding_tolerance=rounding_tolerance)
    )
    findings.extend(
        check_line_items_subtotal(invoice, rounding_tolerance=rounding_tolerance)
    )
    findings.extend(check_invoice_dates(invoice))
    return findings


def check_invoice_total(
    invoice: InvoiceExtraction,
    rounding_tolerance: Decimal = DEFAULT_ROUNDING_TOLERANCE,
) -> list[VerificationFinding]:
    subtotal = invoice.subtotal
    tax = invoice.tax
    discount = invoice.discount
    total = invoice.total
    if subtotal is None or total is None:
        return []

    if tax is None and discount is None:
        if subtotal == total:
            return []
        return []

    tax_val = tax if tax is not None else Decimal(0)
    discount_val = discount if discount is not None else Decimal(0)
    expected_total = subtotal + tax_val - discount_val

    if total == expected_total:
        return []

    discrepancy = abs(total - expected_total)
    if discrepancy <= rounding_tolerance:
        return [
            VerificationFinding(
                finding_type="rounding_discrepancy",
                severity="low",
                explanation=(
                    f"The invoice total has a fractional rounding discrepancy of {discrepancy} "
                    f"within the tolerance of {rounding_tolerance}."
                ),
                comparison_source="invoice_fields",
                deterministic_rule=f"abs(subtotal + tax - discount - total) <= {rounding_tolerance}",
                observed_value=str(total),
                expected_value=str(expected_total),
                details={
                    "currency": invoice.currency,
                    "discrepancy": str(discrepancy),
                    "tolerance": str(rounding_tolerance),
                    "component": "invoice_total",
                },
            )
        ]

    return [
        VerificationFinding(
            finding_type="invoice_total_mismatch",
            severity="high",
            explanation="The invoice total does not equal subtotal plus tax minus discount.",
            comparison_source="invoice_fields",
            deterministic_rule="subtotal + tax - discount == total",
            observed_value=str(total),
            expected_value=str(expected_total),
            details={
                "currency": invoice.currency,
                "discrepancy": str(discrepancy),
                "tolerance": str(rounding_tolerance),
            },
        )
    ]


_check_invoice_total = check_invoice_total


def check_line_item_amounts(
    invoice: InvoiceExtraction,
    rounding_tolerance: Decimal = DEFAULT_ROUNDING_TOLERANCE,
) -> list[VerificationFinding]:
    findings: list[VerificationFinding] = []
    for index, line_item in enumerate(invoice.line_items):
        quantity = line_item.quantity
        unit_price = line_item.unit_price
        total_price = line_item.total_price
        if quantity is None or unit_price is None or total_price is None:
            continue
        expected_total = quantity * unit_price
        if total_price == expected_total:
            continue
        discrepancy = abs(total_price - expected_total)
        if discrepancy <= rounding_tolerance:
            findings.append(
                VerificationFinding(
                    finding_type="rounding_discrepancy",
                    severity="low",
                    explanation=(
                        f"Line item {index} total has a fractional rounding discrepancy of "
                        f"{discrepancy} within the tolerance of {rounding_tolerance}."
                    ),
                    comparison_source="invoice_line_items",
                    deterministic_rule=f"abs(quantity * unit_price - total_price) <= {rounding_tolerance}",
                    observed_value=str(total_price),
                    expected_value=str(expected_total),
                    details={
                        "line_item_index": index,
                        "product_identifier": line_item.product_identifier,
                        "discrepancy": str(discrepancy),
                        "tolerance": str(rounding_tolerance),
                        "component": "line_item_amount",
                    },
                )
            )
        else:
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
                        "discrepancy": str(discrepancy),
                        "tolerance": str(rounding_tolerance),
                    },
                )
            )
    return findings


_check_line_item_amounts = check_line_item_amounts


def check_line_items_subtotal(
    invoice: InvoiceExtraction,
    rounding_tolerance: Decimal = DEFAULT_ROUNDING_TOLERANCE,
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
    discrepancy = abs(invoice.subtotal - expected_subtotal)
    if discrepancy <= rounding_tolerance:
        return [
            VerificationFinding(
                finding_type="rounding_discrepancy",
                severity="low",
                explanation=(
                    f"The line-item sum has a fractional rounding discrepancy of "
                    f"{discrepancy} within the tolerance of {rounding_tolerance}."
                ),
                comparison_source="invoice_line_items",
                deterministic_rule=f"abs(sum(line_item.total_price) - subtotal) <= {rounding_tolerance}",
                observed_value=str(invoice.subtotal),
                expected_value=str(expected_subtotal),
                details={
                    "line_item_count": len(invoice.line_items),
                    "discrepancy": str(discrepancy),
                    "tolerance": str(rounding_tolerance),
                    "component": "line_items_subtotal",
                },
            )
        ]
    return [
        VerificationFinding(
            finding_type="line_items_subtotal_mismatch",
            severity="high",
            explanation="The sum of line-item totals does not equal the invoice subtotal.",
            comparison_source="invoice_line_items",
            deterministic_rule="sum(line_item.total_price) == subtotal",
            observed_value=str(invoice.subtotal),
            expected_value=str(expected_subtotal),
            details={
                "line_item_count": len(invoice.line_items),
                "discrepancy": str(discrepancy),
                "tolerance": str(rounding_tolerance),
            },
        )
    ]


_check_line_items_subtotal = check_line_items_subtotal


def check_invoice_dates(invoice: InvoiceExtraction) -> list[VerificationFinding]:
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


_check_invoice_dates = check_invoice_dates

__all__ = [
    "DEFAULT_ROUNDING_TOLERANCE",
    "check_arithmetic",
    "check_invoice_dates",
    "check_invoice_total",
    "check_line_item_amounts",
    "check_line_items_subtotal",
]
