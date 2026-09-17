"""Explanation guardrail compliance and numerical fidelity metrics."""

from __future__ import annotations

import re
from collections.abc import Sequence

from veridoc.evaluation.models import ExplanationMetrics
from veridoc.explanation.models import FindingExplanation

_NUMBER_PATTERN = re.compile(r"\b\d+(?:\.\d+)?\b")


def detect_numerical_contradictions(explanation: FindingExplanation) -> bool:
    """Check if explanation narrative introduces unauthorized numbers absent from finding evidence."""
    context_numbers = set(_NUMBER_PATTERN.findall(explanation.numerical_context))
    if explanation.finding.observed_value:
        context_numbers.update(
            _NUMBER_PATTERN.findall(explanation.finding.observed_value)
        )
    if explanation.finding.expected_value:
        context_numbers.update(
            _NUMBER_PATTERN.findall(explanation.finding.expected_value)
        )
    if explanation.finding.explanation:
        context_numbers.update(_NUMBER_PATTERN.findall(explanation.finding.explanation))

    narrative_numbers = _NUMBER_PATTERN.findall(explanation.narrative)
    # Check if narrative introduces any new number not present in finding or numerical context
    for num in narrative_numbers:
        if num not in context_numbers:
            return True
    return False


def aggregate_explanation_metrics(
    explanations: Sequence[FindingExplanation],
    *,
    rejected_drafts_count: int = 0,
) -> ExplanationMetrics:
    """Aggregate explanation guardrail passes, fallbacks, and numerical contradiction rates."""
    total_explanations = len(explanations)
    fallback_invocations = 0
    guardrail_passes = 0
    numerical_contradictions = 0

    for exp in explanations:
        if exp.source == "deterministic":
            fallback_invocations += 1
        elif exp.source == "llm":
            guardrail_passes += 1

        if detect_numerical_contradictions(exp):
            numerical_contradictions += 1

    total_evaluations = guardrail_passes + rejected_drafts_count
    pass_rate = guardrail_passes / total_evaluations if total_evaluations > 0 else 1.0

    return ExplanationMetrics(
        total_explanations=total_explanations,
        guardrail_passes=guardrail_passes,
        guardrail_rejections=rejected_drafts_count,
        guardrail_pass_rate=round(pass_rate, 4),
        numerical_contradictions=numerical_contradictions,
        fallback_invocations=fallback_invocations,
    )
