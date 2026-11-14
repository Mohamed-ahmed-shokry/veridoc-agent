"""Deterministic purchase order number syntax, length, and placeholder verification.

In accounts payable (AP) automation and procurement reconciliation, ``purchase_order_number``
references an authorized commercial contract or procurement order. When present on an invoice,
it serves as the foreign key for two-way and three-way purchase order matching, and acts as an
anchor that exempts genuine contracts from stale-invoice flags.

While purchase orders are optional on non-PO invoices (e.g. utilities, recurring leases), vision
and OCR extraction models frequently capture generic placeholder tokens (e.g. "N/A", "NONE",
"NULL", "TBD", "PENDING", "NO PO"), table header labels (e.g. "PO", "PO #", "PO NO",
"PURCHASE ORDER"), embedded control characters or line breaks, pure punctuation (e.g. "-",
"---", "..."), or runaway multi-line text blocks (> 64 characters) when an actual purchase order
number is absent or misaligned on the document.

This module flags invalid, placeholder, and corrupted purchase order numbers with ``medium``
severity, routing invoices to mandatory human review.
"""

from __future__ import annotations

import unicodedata
from typing import Final

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationFinding

MAX_PURCHASE_ORDER_NUMBER_LENGTH: Final[int] = 64

_PLACEHOLDER_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "n/a",
        "na",
        "none",
        "null",
        "nil",
        "unknown",
        "tbd",
        "pending",
        "void",
        "sample",
        "test",
        "undefined",
        "not applicable",
        "not available",
        "unassigned",
        "no po",
        "no p.o.",
        "none required",
        "verbal",
        "verbal po",
    }
)

_GENERIC_LABEL_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "po",
        "po number",
        "po no",
        "po #",
        "po num",
        "purchase order",
        "purchase order number",
        "purchase order no",
        "purchase order #",
        "p.o.",
        "p.o. #",
        "p.o. no",
        "order number",
        "order no",
        "order #",
        "order",
        "po/so",
        "so",
        "#",
    }
)


def is_valid_purchase_order_number(
    raw_number: str | None,
    max_length: int = MAX_PURCHASE_ORDER_NUMBER_LENGTH,
) -> bool:
    """Return True if raw_number is a structurally valid, non-placeholder purchase order identifier."""
    if raw_number is None:
        return False

    if any(
        c in "\r\n\t" or (unicodedata.category(c).startswith("C") and c != " ")
        for c in raw_number
    ):
        return False

    cleaned = raw_number.strip()
    if not cleaned or not any(c.isalnum() for c in cleaned):
        return False

    if len(cleaned) > max_length:
        return False

    normalized = " ".join(cleaned.lower().split())
    return (
        normalized not in _PLACEHOLDER_TOKENS
        and normalized not in _GENERIC_LABEL_TOKENS
    )


def check_purchase_order_number_format(
    invoice: InvoiceExtraction,
    max_length: int = MAX_PURCHASE_ORDER_NUMBER_LENGTH,
) -> list[VerificationFinding]:
    """Flag invoices whose purchase order number is a placeholder, label, or invalid syntax.

    Args:
        invoice: The extracted invoice data to verify.
        max_length: Maximum permitted length for a purchase order number. Defaults to 64.

    Returns:
        A list containing one ``invalid_purchase_order_number`` finding (severity="medium")
        if ``invoice.purchase_order_number`` is present and invalid, or an empty list
        if it is valid or absent (``None``).
    """
    raw_number = invoice.purchase_order_number
    if raw_number is None:
        return []

    # Check for unprintable control characters, newlines, or tabs
    if any(
        c in "\r\n\t" or (unicodedata.category(c).startswith("C") and c != " ")
        for c in raw_number
    ):
        return [
            _build_finding(
                raw_number,
                reason="control_characters",
                explanation=(
                    f"The extracted purchase order number ({raw_number!r}) contains invalid control "
                    "characters or line breaks."
                ),
            )
        ]

    cleaned = raw_number.strip()
    if not cleaned or not any(c.isalnum() for c in cleaned):
        return [
            _build_finding(
                raw_number,
                reason="blank_or_punctuation",
                explanation=(
                    f"The extracted purchase order number ({raw_number!r}) contains no alphanumeric characters."
                ),
            )
        ]

    if len(cleaned) > max_length:
        return [
            _build_finding(
                raw_number,
                reason="excessive_length",
                explanation=(
                    f"The extracted purchase order number length ({len(cleaned)}) exceeds the maximum "
                    f"allowed length of {max_length} characters."
                ),
            )
        ]

    normalized = " ".join(cleaned.lower().split())
    if normalized in _PLACEHOLDER_TOKENS:
        return [
            _build_finding(
                raw_number,
                reason="placeholder",
                explanation=(
                    f"The extracted purchase order number ({raw_number!r}) is a generic placeholder "
                    "token rather than an authorizing purchase order identifier."
                ),
            )
        ]

    if normalized in _GENERIC_LABEL_TOKENS:
        return [
            _build_finding(
                raw_number,
                reason="generic_label",
                explanation=(
                    f"The extracted purchase order number ({raw_number!r}) contains a document header "
                    "label rather than an authorizing purchase order identifier."
                ),
            )
        ]

    return []


def _build_finding(
    raw_number: str,
    *,
    reason: str,
    explanation: str,
) -> VerificationFinding:
    return VerificationFinding(
        finding_type="invalid_purchase_order_number",
        severity="medium",
        explanation=explanation,
        comparison_source="invoice_fields",
        deterministic_rule="invoice.purchase_order_number is a valid alphanumeric identifier and not a placeholder",
        observed_value=raw_number,
        expected_value="valid purchase order number",
        details={
            "field": "purchase_order_number",
            "purchase_order_number": raw_number,
            "reason": reason,
        },
    )


__all__ = [
    "MAX_PURCHASE_ORDER_NUMBER_LENGTH",
    "check_purchase_order_number_format",
    "is_valid_purchase_order_number",
]
