"""Typed verification finding contract tests."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from veridoc.verification.models import VerificationFinding, VerificationResult


def test_verification_finding_preserves_structured_statistical_evidence() -> None:
    finding = VerificationFinding(
        finding_type="historical_total_outlier",
        severity="high",
        explanation="The invoice total is outside the established vendor range.",
        comparison_source="vendor_history",
        deterministic_rule="absolute_z_score >= 3",
        observed_value="18400.00",
        expected_range=("5600.00", "8800.00"),
        historical_sample_size=6,
        historical_mean="7200.00",
        historical_standard_deviation="1600.00",
        z_score="7.00",
        details={"currency": "USD"},
    )

    assert finding.historical_mean == Decimal("7200.00")
    assert finding.expected_range == ("5600.00", "8800.00")
    assert VerificationResult(findings=[finding]).findings == [finding]


def test_verification_finding_rejects_invalid_evidence() -> None:
    with pytest.raises(ValidationError):
        VerificationFinding(
            finding_type="unknown",
            severity="high",
            explanation="Invalid finding type.",
            comparison_source="vendor_history",
            deterministic_rule="rule",
        )
    with pytest.raises(ValidationError):
        VerificationFinding(
            finding_type="insufficient_history",
            severity="info",
            explanation="",
            comparison_source="vendor_history",
            deterministic_rule="sample_size < 3",
        )
    with pytest.raises(ValidationError):
        VerificationResult(unexpected="value")


def test_verification_finding_accepts_duplicate_line_item() -> None:
    finding = VerificationFinding(
        finding_type="duplicate_line_item",
        severity="high",
        explanation="Line item 1 is a duplicate of line item 0.",
        comparison_source="invoice_line_items",
        deterministic_rule="line items within an invoice must be unique by product identifier or description",
        observed_value="product:sku-100",
        expected_value="unique line item",
        details={"line_item_index": 1, "duplicate_of_index": 0, "match_type": "exact"},
    )
    assert finding.finding_type == "duplicate_line_item"
    assert finding.severity == "high"
