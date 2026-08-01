"""Typed outputs produced by deterministic invoice verification."""

from __future__ import annotations

from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

ComparisonSource = Literal[
    "invoice_fields",
    "invoice_line_items",
    "purchase_order",
    "vendor_history",
    "invoice_register",
]
FindingSeverity = Literal["info", "low", "medium", "high"]
FindingType = Literal[
    "invoice_total_mismatch",
    "line_item_amount_mismatch",
    "line_items_subtotal_mismatch",
    "invoice_date_after_due_date",
    "purchase_order_mismatch",
    "duplicate_invoice_number",
    "historical_total_outlier",
    "historical_line_item_price_outlier",
    "historical_line_item_quantity_outlier",
    "new_line_item",
    "rare_line_item",
    "payment_terms_changed",
    "missing_historical_field",
    "insufficient_history",
]


class VerificationFinding(BaseModel):
    """One deterministic finding and the data used to derive it."""

    model_config = ConfigDict(extra="forbid")

    finding_type: FindingType
    severity: FindingSeverity
    explanation: str = Field(min_length=1)
    comparison_source: ComparisonSource
    deterministic_rule: str = Field(min_length=1)
    observed_value: str | None = None
    expected_value: str | None = None
    expected_range: tuple[str, str] | None = None
    historical_sample_size: int | None = Field(default=None, ge=0)
    historical_mean: Decimal | None = None
    historical_standard_deviation: Decimal | None = None
    z_score: Decimal | None = None
    details: dict[str, str | int | float | bool | None] = Field(default_factory=dict)


class VerificationResult(BaseModel):
    """All deterministic findings for one extracted invoice."""

    model_config = ConfigDict(extra="forbid")

    findings: list[VerificationFinding] = Field(default_factory=list)
