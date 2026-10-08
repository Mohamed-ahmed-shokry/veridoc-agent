"""Deterministic non-positive line-item detection check.

In commercial accounts payable and document intelligence, an invoice
(document_type="invoice") represents an instrument requesting payment for
goods or services delivered. Under standard accounting principles (GAAP, IFRS)
and business controls, commercial line items must specify strictly positive
values for quantity (quantity > 0), unit price (unit_price > 0), and line total
(total_price > 0).

A line item with a negative total, unit price, or quantity indicates an
unauthorized credit line, return allowance, trade-in deduction, or rebate
offset embedded directly into an invoice. In accounts payable workflows, credits
cannot be netted against standard billing without explicit credit memo
authorization and debit-reversal processing. Netting negative line items
distorts sales tax / VAT calculations across mixed-rate supplies, bypasses
purchase-order line authorization ceilings, and evades AP approval thresholds.
Furthermore, negative line items frequently arise from vision/OCR extraction
defects where hyphens, dashes, bullet points, or glyphs are erroneously
transcribed as negative signs.

A line item specifying a zero quantity (quantity == 0) indicates an operational
anomaly: billing for goods or services where zero units were delivered. A line
item with a zero unit price or zero line total (unit_price == 0 or total_price == 0)
represents promotional samples, zero-dollar warranty replacements, unpriced
services, or an OCR extraction dropout where the price was blanked or misparsed
as zero.

This check detects non-positive line items, assigning high severity if any
observed field on the line item is negative (< 0) and medium severity if all
observed non-positive fields are zero (== 0).
"""

from __future__ import annotations

from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem
from veridoc.verification.models import FindingSeverity, VerificationFinding


def check_non_positive_line_items(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Return findings for invoice line items with non-positive values.

    Args:
        invoice: The structured invoice extraction to check.

    Returns:
        A list of ``non_positive_line_item`` findings, one for each line item
        with at least one observed non-positive field (<= 0). Line items with
        any negative field (< 0) produce ``high`` severity findings; line items
        with only zero fields (== 0) produce ``medium`` severity findings.
        Line items with empty or strictly positive fields produce no findings.
    """
    findings: list[VerificationFinding] = []
    for index, line_item in enumerate(invoice.line_items):
        finding = _check_line_item(index, line_item)
        if finding is not None:
            findings.append(finding)
    return findings


def _check_line_item(
    index: int, line_item: InvoiceLineItem
) -> VerificationFinding | None:
    non_positive_fields: list[tuple[str, Decimal]] = []

    if line_item.quantity is not None and line_item.quantity <= Decimal(0):
        non_positive_fields.append(("quantity", line_item.quantity))

    if line_item.unit_price is not None and line_item.unit_price <= Decimal(0):
        non_positive_fields.append(("unit_price", line_item.unit_price))

    if line_item.total_price is not None and line_item.total_price <= Decimal(0):
        non_positive_fields.append(("total_price", line_item.total_price))

    if not non_positive_fields:
        return None

    is_negative = any(value < Decimal(0) for _, value in non_positive_fields)
    severity: FindingSeverity = "high" if is_negative else "medium"

    field_names = [name for name, _ in non_positive_fields]
    field_summary = ", ".join(field_names)
    observed_parts = [f"{name}={value}" for name, value in non_positive_fields]
    observed_value = ", ".join(observed_parts)

    label_part = ""
    if line_item.product_identifier:
        label_part = f" ('{line_item.product_identifier}')"
    elif line_item.description:
        label_part = f" ('{line_item.description}')"

    if is_negative:
        explanation = (
            f"Line item {index}{label_part} has negative {field_summary} ({observed_value}). "
            "Negative line items indicate credit lines, returns, or billing adjustments "
            "requiring review."
        )
    else:
        explanation = (
            f"Line item {index}{label_part} has zero {field_summary} ({observed_value}). "
            "Zero-value line items indicate pro-forma samples, placeholder lines, "
            "or extraction errors requiring review."
        )

    details: dict[str, str | int | float | bool | None] = {
        "line_item_index": index,
        "field": field_summary,
        "is_zero": not is_negative,
        "is_negative": is_negative,
    }
    if line_item.product_identifier is not None:
        details["product_identifier"] = line_item.product_identifier
    if line_item.description is not None:
        details["description"] = line_item.description
    for name, value in non_positive_fields:
        details[name] = str(value)

    return VerificationFinding(
        finding_type="non_positive_line_item",
        severity=severity,
        explanation=explanation,
        comparison_source="invoice_line_items",
        deterministic_rule="line_item.quantity > 0 and line_item.unit_price > 0 and line_item.total_price > 0",
        observed_value=observed_value,
        expected_value="> 0.00",
        details=details,
    )
