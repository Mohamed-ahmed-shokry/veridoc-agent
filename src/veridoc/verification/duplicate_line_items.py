"""Deterministic duplicate line-item detection within an invoice.

Repeated or duplicate line items on a single invoice are a primary pattern in
accounts payable billing errors, intentional double-billing fraud, and OCR
table extraction artifacts (such as repeated bounding boxes or table headers
re-read across page boundaries).

Because the arithmetic verification engine validates the subtotal against the sum
of line-item amounts (sum(line_items) == subtotal), an invoice containing duplicated
line items will pass arithmetic checks without warning. This check detects
duplicate line items within the invoice by canonicalizing product identifiers and
descriptions, flagging exact duplicates with high severity and partial/split
duplicates with medium severity.
"""

from __future__ import annotations

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.line_items import line_item_key
from veridoc.verification.models import FindingSeverity, VerificationFinding


def check_duplicate_line_items(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Return findings for duplicate line items within a single invoice.

    Args:
        invoice: The extracted invoice to inspect.

    Returns:
        A list of ``duplicate_line_item`` findings, one for each duplicate
        occurrence after the first. Exact matches (identical quantity and
        unit price) produce ``high`` severity findings; partial matches
        (differing or missing quantity/unit price) produce ``medium``
        severity findings.
    """
    if not invoice.line_items or len(invoice.line_items) <= 1:
        return []

    seen_keys: dict[str, int] = {}
    findings: list[VerificationFinding] = []

    for index, line_item in enumerate(invoice.line_items):
        key = line_item_key(line_item.product_identifier, line_item.description)
        if key is None:
            continue

        if key not in seen_keys:
            seen_keys[key] = index
            continue

        first_index = seen_keys[key]
        first_line_item = invoice.line_items[first_index]

        is_exact = (
            line_item.quantity is not None
            and line_item.unit_price is not None
            and line_item.quantity == first_line_item.quantity
            and line_item.unit_price == first_line_item.unit_price
        )

        severity: FindingSeverity = "high" if is_exact else "medium"
        match_type = "exact" if is_exact else "partial"

        if is_exact:
            explanation = (
                f"Line item {index} is an exact duplicate of line item {first_index} "
                f"with identical description, quantity ({line_item.quantity}), "
                f"and unit price ({line_item.unit_price}). Repeated identical line items "
                "indicate double-billing or OCR duplication errors."
            )
        else:
            explanation = (
                f"Line item {index} shares product identifier or description with "
                f"line item {first_index} but has differing quantity or unit price. "
                "Repeated line items warrant review to prevent split over-billing."
            )

        findings.append(
            VerificationFinding(
                finding_type="duplicate_line_item",
                severity=severity,
                explanation=explanation,
                comparison_source="invoice_line_items",
                deterministic_rule=(
                    "line items within an invoice must be unique by product "
                    "identifier or description"
                ),
                observed_value=key,
                expected_value="unique line item",
                details={
                    "line_item_index": index,
                    "duplicate_of_index": first_index,
                    "match_type": match_type,
                    "key": key,
                    "product_identifier": line_item.product_identifier,
                    "description": line_item.description,
                    "quantity": (
                        str(line_item.quantity)
                        if line_item.quantity is not None
                        else None
                    ),
                    "unit_price": (
                        str(line_item.unit_price)
                        if line_item.unit_price is not None
                        else None
                    ),
                },
            )
        )

    return findings
