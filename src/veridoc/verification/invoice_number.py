"""Deterministic invoice number syntax, length, and placeholder verification.

In commercial accounts payable (AP) and enterprise resource planning (ERP) systems,
``invoice_number`` is the primary vendor-scoped billing identifier. It is required for
three-way purchase-order matching, duplicate invoice detection, and payment remittance.

While Phase 33 mandates that ``invoice_number`` must not be ``None``, vision and OCR
models frequently extract generic placeholder values (e.g. "N/A", "NONE", "NULL"),
column headers or labels (e.g. "INVOICE", "INV #", "BILL NO"), pure punctuation
(e.g. "-", "/", "."), multi-line text blocks with line breaks, or runaway paragraphs
(> 64 characters) when an invoice number is missing or misaligned on the document.

This module flags invalid, placeholder, and corrupted invoice numbers with ``high``
severity, routing invoices to mandatory human review.
"""

from __future__ import annotations

import unicodedata
from typing import Final

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationFinding

MAX_INVOICE_NUMBER_LENGTH: Final[int] = 64

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
    }
)

_GENERIC_LABEL_TOKENS: Final[frozenset[str]] = frozenset(
    {
        "invoice",
        "invoice number",
        "invoice no",
        "invoice #",
        "invoice num",
        "inv",
        "inv no",
        "inv #",
        "inv num",
        "bill",
        "bill no",
        "bill #",
        "number",
        "no",
        "#",
    }
)


def check_invoice_number_format(
    invoice: InvoiceExtraction,
    max_length: int = MAX_INVOICE_NUMBER_LENGTH,
) -> list[VerificationFinding]:
    """Flag invoices whose invoice number is a placeholder, label, or invalid syntax.

    Args:
        invoice: The extracted invoice data to verify.
        max_length: Maximum permitted length for an invoice number. Defaults to 64.

    Returns:
        A list containing one ``invalid_invoice_number`` finding (severity="high")
        if ``invoice.invoice_number`` is present and invalid, or an empty list
        if it is valid or absent (``None``).
    """
    raw_number = invoice.invoice_number
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
                    f"The extracted invoice number ({raw_number!r}) contains invalid control "
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
                    f"The extracted invoice number ({raw_number!r}) contains no alphanumeric characters."
                ),
            )
        ]

    if len(cleaned) > max_length:
        return [
            _build_finding(
                raw_number,
                reason="excessive_length",
                explanation=(
                    f"The extracted invoice number length ({len(cleaned)}) exceeds the maximum "
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
                    f"The extracted invoice number ({raw_number!r}) is a generic placeholder "
                    "token rather than a valid transaction identifier."
                ),
            )
        ]

    if normalized in _GENERIC_LABEL_TOKENS:
        return [
            _build_finding(
                raw_number,
                reason="generic_label",
                explanation=(
                    f"The extracted invoice number ({raw_number!r}) contains a document header "
                    "label rather than a transaction identifier."
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
        finding_type="invalid_invoice_number",
        severity="high",
        explanation=explanation,
        comparison_source="invoice_fields",
        deterministic_rule="invoice.invoice_number is a valid alphanumeric identifier and not a placeholder",
        observed_value=raw_number,
        expected_value="valid invoice number",
        details={
            "field": "invoice_number",
            "invoice_number": raw_number,
            "reason": reason,
        },
    )


__all__ = [
    "MAX_INVOICE_NUMBER_LENGTH",
    "check_invoice_number_format",
]
