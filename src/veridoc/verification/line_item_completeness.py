"""Checks that every invoice line item can be identified and priced."""

from __future__ import annotations

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.line_items import line_item_key
from veridoc.verification.models import VerificationFinding


def check_line_item_completeness(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Report line items that cannot be identified or priced deterministically."""
    findings: list[VerificationFinding] = []
    for index, line_item in enumerate(invoice.line_items):
        if line_item_key(line_item.product_identifier, line_item.description) is None:
            findings.append(
                VerificationFinding(
                    finding_type="incomplete_line_item",
                    severity="medium",
                    explanation=(
                        f"Line item {index} has neither a product identifier nor a "
                        "description, so it cannot be matched to purchase orders or "
                        "vendor history."
                    ),
                    comparison_source="invoice_line_items",
                    deterministic_rule=(
                        "line_item.product_identifier or line_item.description is present"
                    ),
                    observed_value=None,
                    expected_value="identity",
                    details={"line_item_index": index, "field": "identity"},
                )
            )
        if line_item.total_price is None and (
            line_item.quantity is None or line_item.unit_price is None
        ):
            findings.append(
                VerificationFinding(
                    finding_type="incomplete_line_item",
                    severity="medium",
                    explanation=(
                        f"Line item {index} has no total price and lacks the quantity "
                        "and unit price needed to derive one, so its amount cannot be "
                        "verified."
                    ),
                    comparison_source="invoice_line_items",
                    deterministic_rule=(
                        "line_item.total_price is not None or "
                        "(line_item.quantity is not None and line_item.unit_price is not None)"
                    ),
                    observed_value=None,
                    expected_value="amount",
                    details={"line_item_index": index, "field": "amount"},
                )
            )
    return findings
