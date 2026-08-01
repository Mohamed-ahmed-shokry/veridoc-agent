"""Deterministic, evidence-grounded explanation rendering."""

from __future__ import annotations

from veridoc.explanation.models import ExplanationResult, FindingExplanation
from veridoc.verification.models import VerificationFinding, VerificationResult


def render_deterministic_explanations(
    verification: VerificationResult,
) -> ExplanationResult:
    """Render every verified finding without an external model dependency."""
    return ExplanationResult(
        explanations=[
            render_deterministic_explanation(finding)
            for finding in verification.findings
        ]
    )


def render_deterministic_explanation(
    finding: VerificationFinding,
) -> FindingExplanation:
    """Render one finding using only its deterministic evidence fields."""
    return FindingExplanation(
        finding=finding,
        narrative=(
            f"{finding.explanation} Deterministic rule evaluated: "
            f"{finding.deterministic_rule}."
        ),
        numerical_context=_numerical_context(finding),
        source="deterministic",
    )


def _numerical_context(finding: VerificationFinding) -> str:
    context: list[str] = []
    if finding.observed_value is not None:
        context.append(f"Observed value: {finding.observed_value}.")
    if finding.expected_value is not None:
        context.append(f"Expected value: {finding.expected_value}.")
    if finding.expected_range is not None:
        lower_bound, upper_bound = finding.expected_range
        context.append(f"Expected range: {lower_bound} to {upper_bound}.")
    if finding.historical_sample_size is not None:
        context.append(f"Historical sample size: {finding.historical_sample_size}.")
    if finding.historical_mean is not None:
        context.append(f"Historical mean: {finding.historical_mean}.")
    if finding.historical_standard_deviation is not None:
        context.append(
            f"Historical standard deviation: {finding.historical_standard_deviation}."
        )
    if finding.z_score is not None:
        context.append(f"Z-score: {finding.z_score}.")
    return (
        " ".join(context) or "No numerical comparison was available for this finding."
    )
