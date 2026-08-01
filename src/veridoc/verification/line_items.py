"""Deterministic vendor-history checks for invoice line-item occurrence."""

from __future__ import annotations

import re
from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.history import (
    MINIMUM_HISTORY_SAMPLE_SIZE,
    OUTLIER_Z_SCORE,
    _population_standard_deviation,
)
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


def check_line_item_statistics(
    invoice: InvoiceExtraction, history: list[HistoricalInvoice]
) -> list[VerificationFinding]:
    """Compare line-item prices and quantities with matching vendor history."""
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
        historical_line_items = [
            historical_line_item
            for historical_invoice in comparable_history
            for historical_line_item in historical_invoice.line_items
            if line_item_key(
                historical_line_item.product_identifier,
                historical_line_item.description,
            )
            == key
        ]
        findings.extend(
            _check_metric(
                observed_value=line_item.unit_price,
                historical_values=[
                    historical_line_item.unit_price
                    for historical_line_item in historical_line_items
                    if historical_line_item.unit_price is not None
                ],
                finding_type="historical_line_item_price_outlier",
                metric="line_item_unit_price",
                key=key,
                index=index,
            )
        )
        findings.extend(
            _check_metric(
                observed_value=line_item.quantity,
                historical_values=[
                    historical_line_item.quantity
                    for historical_line_item in historical_line_items
                    if historical_line_item.quantity is not None
                ],
                finding_type="historical_line_item_quantity_outlier",
                metric="line_item_quantity",
                key=key,
                index=index,
            )
        )
    return findings


def _check_metric(
    *,
    observed_value: Decimal | None,
    historical_values: list[Decimal],
    finding_type: str,
    metric: str,
    key: str,
    index: int,
) -> list[VerificationFinding]:
    if observed_value is None:
        return []
    if len(historical_values) < MINIMUM_HISTORY_SAMPLE_SIZE:
        return [
            VerificationFinding(
                finding_type="insufficient_history",
                severity="info",
                explanation="There are not enough matching line items for a reliable comparison.",
                comparison_source="vendor_history",
                deterministic_rule=f"sample_size >= {MINIMUM_HISTORY_SAMPLE_SIZE}",
                observed_value=str(observed_value),
                historical_sample_size=len(historical_values),
                details={
                    "metric": metric,
                    "line_item_key": key,
                    "line_item_index": index,
                    "required_sample_size": MINIMUM_HISTORY_SAMPLE_SIZE,
                },
            )
        ]

    mean = sum(historical_values) / len(historical_values)
    standard_deviation = _population_standard_deviation(historical_values, mean)
    if standard_deviation == 0:
        return _check_zero_variance_metric(
            observed_value,
            mean,
            len(historical_values),
            finding_type,
            metric,
            key,
            index,
        )

    z_score = abs(observed_value - mean) / standard_deviation
    if z_score < OUTLIER_Z_SCORE:
        return []
    lower_bound = mean - (OUTLIER_Z_SCORE * standard_deviation)
    upper_bound = mean + (OUTLIER_Z_SCORE * standard_deviation)
    return [
        VerificationFinding(
            finding_type=finding_type,
            severity="high",
            explanation="The line-item value is outside the vendor's established range.",
            comparison_source="vendor_history",
            deterministic_rule="absolute_z_score >= 3",
            observed_value=str(observed_value),
            expected_range=(str(lower_bound), str(upper_bound)),
            historical_sample_size=len(historical_values),
            historical_mean=mean,
            historical_standard_deviation=standard_deviation,
            z_score=z_score,
            details={
                "metric": metric,
                "line_item_key": key,
                "line_item_index": index,
            },
        )
    ]


def _check_zero_variance_metric(
    observed_value: Decimal,
    mean: Decimal,
    sample_size: int,
    finding_type: str,
    metric: str,
    key: str,
    index: int,
) -> list[VerificationFinding]:
    if observed_value == mean:
        return []
    return [
        VerificationFinding(
            finding_type=finding_type,
            severity="high",
            explanation="The line-item value differs from a uniform vendor history.",
            comparison_source="vendor_history",
            deterministic_rule="standard_deviation == 0 and observed_value != mean",
            observed_value=str(observed_value),
            expected_value=str(mean),
            historical_sample_size=sample_size,
            historical_mean=mean,
            historical_standard_deviation=Decimal(0),
            details={
                "metric": metric,
                "line_item_key": key,
                "line_item_index": index,
            },
        )
    ]


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
