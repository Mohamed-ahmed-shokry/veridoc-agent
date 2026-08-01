"""Deterministic explanation rendering tests."""

from veridoc.explanation.fallback import render_deterministic_explanations
from veridoc.verification.models import VerificationFinding, VerificationResult


def test_deterministic_explanation_preserves_statistical_context() -> None:
    verification = VerificationResult(
        findings=[
            VerificationFinding(
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
        ]
    )

    result = render_deterministic_explanations(verification)

    explanation = result.explanations[0]
    assert explanation.source == "deterministic"
    assert "absolute_z_score >= 3" in explanation.narrative
    assert explanation.numerical_context == (
        "Observed value: 18400.00. Expected range: 5600.00 to 8800.00. "
        "Historical sample size: 6. Historical mean: 7200.00. "
        "Historical standard deviation: 1600.00. Z-score: 7.00."
    )


def test_deterministic_explanation_declares_when_no_numbers_are_available() -> None:
    verification = VerificationResult(
        findings=[
            VerificationFinding(
                finding_type="duplicate_invoice_number",
                severity="high",
                explanation="This vendor already has an invoice with the extracted invoice number.",
                comparison_source="invoice_register",
                deterministic_rule="invoice_number must be unique within a vendor history",
            )
        ]
    )

    result = render_deterministic_explanations(verification)

    assert result.explanations[0].numerical_context == (
        "No numerical comparison was available for this finding."
    )
