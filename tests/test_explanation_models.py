"""Typed explanation result contract tests."""

import pytest
from pydantic import ValidationError

from veridoc.explanation.models import ExplanationResult, FindingExplanation
from veridoc.verification.models import VerificationFinding


def _finding() -> VerificationFinding:
    return VerificationFinding(
        finding_type="historical_total_outlier",
        severity="high",
        explanation="The invoice total is outside the vendor's established range.",
        comparison_source="vendor_history",
        deterministic_rule="absolute_z_score >= 3",
        observed_value="18400.00",
        expected_range=("5600.00", "8800.00"),
        historical_sample_size=6,
        historical_mean="7200.00",
        historical_standard_deviation="1600.00",
        z_score="7.00",
    )


def test_finding_explanation_preserves_its_verified_evidence() -> None:
    finding = _finding()
    explanation = FindingExplanation(
        finding=finding,
        narrative="The amount warrants review against the vendor's prior invoices.",
        numerical_context="Observed 18400.00; expected range 5600.00 to 8800.00.",
        source="deterministic",
    )

    result = ExplanationResult(explanations=[explanation])

    assert result.explanations[0].finding == finding
    assert result.explanations[0].source == "deterministic"


def test_explanation_models_reject_empty_or_unexpected_content() -> None:
    with pytest.raises(ValidationError):
        FindingExplanation(
            finding=_finding(),
            narrative="",
            numerical_context="Observed 18400.00.",
            source="deterministic",
        )
    with pytest.raises(ValidationError):
        ExplanationResult(unexpected="value")
