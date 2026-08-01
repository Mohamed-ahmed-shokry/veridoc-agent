"""Deterministic vendor-history checks for invoice line-item occurrence."""

from __future__ import annotations

import re
from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.history import MINIMUM_HISTORY_SAMPLE_SIZE
from veridoc.verification.models import VerificationFinding
from veridoc.verification.references import HistoricalInvoice

RARE_LINE_ITEM_MAX_FREQUENCY = Decimal("0.2")
_WHITESPACE = re.compile(r"\s+")


def check_line_item_occurrence(
    invoice: InvoiceExtraction, history: list[HistoricalInvoice]
) -> list[VerificationFinding]:
    """Report new or rare line items using same-currency invoice history."""
    comparable_history = [
        historical_invoice
        for historical_invoice in history
        if historical_invoice.currency == invoice.currency
    ]
    findings: list[VerificationFinding] = []
    for index, line_item in enumerate(invoice.line_items):
        key = line_item_key(line_item.product_identifier, line_item.description)
        if key is None:
            continue
        if len(comparable_history) < MINIMUM_HISTORY_SAMPLE_SIZE:
            findings.append(
                _insufficient_history_finding(key, index, len(comparable_history))
            )
            continue

        occurrence_count = sum(
            any(
                line_item_key(
                    historical_line_item.product_identifier,
                    historical_line_item.description,
                )
                == key
                for historical_line_item in historical_invoice.line_items
            )
            for historical_invoice in comparable_history
        )
        if occurrence_count == 0:
            findings.append(_new_line_item_finding(key, index, len(comparable_history)))
            continue

        frequency = Decimal(occurrence_count) / Decimal(len(comparable_history))
        if frequency <= RARE_LINE_ITEM_MAX_FREQUENCY:
            findings.append(
                _rare_line_item_finding(
                    key, index, occurrence_count, len(comparable_history), frequency
                )
            )
    return findings


def line_item_key(
    product_identifier: str | None, description: str | None
) -> str | None:
    """Return a deterministic line-item comparison key without inferring values."""
    if product_identifier is not None and product_identifier.strip():
        return f"product:{_normalize_key_part(product_identifier)}"
    if description is not None and description.strip():
        return f"description:{_normalize_key_part(description)}"
    return None


def _new_line_item_finding(
    key: str, index: int, sample_size: int
) -> VerificationFinding:
    return VerificationFinding(
        finding_type="new_line_item",
        severity="medium",
        explanation="The line item has not appeared in the vendor's comparable history.",
        comparison_source="vendor_history",
        deterministic_rule="line_item_occurrence_count == 0",
        observed_value=key,
        expected_value="previously observed line item",
        historical_sample_size=sample_size,
        details={"line_item_index": index},
    )


def _rare_line_item_finding(
    key: str,
    index: int,
    occurrence_count: int,
    sample_size: int,
    frequency: Decimal,
) -> VerificationFinding:
    return VerificationFinding(
        finding_type="rare_line_item",
        severity="low",
        explanation="The line item appears infrequently in the vendor's comparable history.",
        comparison_source="vendor_history",
        deterministic_rule="line_item_frequency <= 0.2",
        observed_value=key,
        expected_range=("0", str(RARE_LINE_ITEM_MAX_FREQUENCY)),
        historical_sample_size=sample_size,
        details={
            "line_item_index": index,
            "occurrence_count": occurrence_count,
            "frequency": str(frequency),
        },
    )


def _insufficient_history_finding(
    key: str, index: int, sample_size: int
) -> VerificationFinding:
    return VerificationFinding(
        finding_type="insufficient_history",
        severity="info",
        explanation="There are not enough comparable invoices to assess line-item occurrence.",
        comparison_source="vendor_history",
        deterministic_rule=f"sample_size >= {MINIMUM_HISTORY_SAMPLE_SIZE}",
        observed_value=key,
        historical_sample_size=sample_size,
        details={
            "metric": "line_item_occurrence",
            "line_item_index": index,
            "required_sample_size": MINIMUM_HISTORY_SAMPLE_SIZE,
        },
    )


def _normalize_key_part(value: str) -> str:
    return _WHITESPACE.sub(" ", value.casefold().strip())
