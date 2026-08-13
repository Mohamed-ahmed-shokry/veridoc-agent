"""Explanation service composition tests with mocked provider boundaries."""

import pytest

from veridoc.explanation.protocol import (
    ExplanationDraft,
    ExplanationDraftResult,
    ExplanationRequest,
    ExplanationUnavailableError,
)
from veridoc.explanation.service import ExplanationService
from veridoc.verification.models import VerificationFinding, VerificationResult


class SafeExplainer:
    """Mocked provider with nonfactual review guidance."""

    async def explain(self, request: ExplanationRequest) -> ExplanationDraftResult:
        assert len(request.findings) == 1
        return ExplanationDraftResult(
            drafts=[
                ExplanationDraft(
                    finding_index=0,
                    narrative="Confirm the supplied evidence before taking action.",
                )
            ]
        )


class ContradictoryExplainer:
    """Mocked provider that invents a numerical claim."""

    async def explain(self, request: ExplanationRequest) -> ExplanationDraftResult:
        return ExplanationDraftResult(
            drafts=[
                ExplanationDraft(
                    finding_index=0,
                    narrative="The total is 100.00 and needs review.",
                )
            ]
        )


class UnavailableExplainer:
    """Mocked provider that cannot be used."""

    async def explain(self, request: ExplanationRequest) -> ExplanationDraftResult:
        raise ExplanationUnavailableError


class MalformedExplainer:
    """Mocked provider that violates the typed draft-result contract."""

    async def explain(self, request: ExplanationRequest) -> object:
        del request
        return None


def _verification() -> VerificationResult:
    return VerificationResult(
        findings=[
            VerificationFinding(
                finding_type="historical_total_outlier",
                severity="high",
                explanation="The invoice total is outside the vendor's established range.",
                comparison_source="vendor_history",
                deterministic_rule="absolute_z_score >= 3",
                observed_value="18400.00",
                expected_range=("5600.00", "8800.00"),
            )
        ]
    )


@pytest.mark.anyio
async def test_service_uses_safe_provider_guidance_with_deterministic_numbers() -> None:
    result = await ExplanationService(SafeExplainer()).explain(_verification())

    explanation = result.explanations[0]
    assert explanation.source == "llm"
    assert (
        explanation.narrative == "Confirm the supplied evidence before taking action."
    )
    assert explanation.numerical_context == (
        "Observed value: 18400.00. Expected range: 5600.00 to 8800.00."
    )


@pytest.mark.anyio
async def test_service_falls_back_when_provider_is_contradictory_or_unavailable() -> (
    None
):
    contradictory = await ExplanationService(ContradictoryExplainer()).explain(
        _verification()
    )
    unavailable = await ExplanationService(UnavailableExplainer()).explain(
        _verification()
    )
    malformed = await ExplanationService(MalformedExplainer()).explain(_verification())

    assert contradictory.explanations[0].source == "deterministic"
    assert unavailable.explanations[0].source == "deterministic"
    assert malformed.explanations[0].source == "deterministic"
