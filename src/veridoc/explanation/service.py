"""API-neutral composition of explanation proposals and deterministic evidence."""

from __future__ import annotations

from veridoc.explanation.fallback import render_deterministic_explanations
from veridoc.explanation.guardrails import validated_narratives
from veridoc.explanation.models import ExplanationResult, FindingExplanation
from veridoc.explanation.protocol import (
    ExplanationProcessingError,
    ExplanationRequest,
    ExplanationUnavailableError,
    FindingExplainer,
)
from veridoc.verification.models import VerificationResult


class ExplanationService:
    """Produce explanations without coupling callers to a provider SDK."""

    def __init__(self, explainer: FindingExplainer | None = None) -> None:
        self._explainer = explainer

    async def explain(self, verification: VerificationResult) -> ExplanationResult:
        """Return grounded provider guidance or a deterministic fallback."""
        fallback = render_deterministic_explanations(verification)
        if self._explainer is None or not verification.findings:
            return fallback

        request = ExplanationRequest.from_verification(verification)
        try:
            drafts = await self._explainer.explain(request)
        except (ExplanationUnavailableError, ExplanationProcessingError):
            return fallback

        narratives = validated_narratives(request, drafts)
        if narratives is None:
            return fallback
        return ExplanationResult(
            explanations=[
                FindingExplanation(
                    finding=finding,
                    narrative=narrative,
                    numerical_context=fallback.explanations[index].numerical_context,
                    source="llm",
                )
                for index, (finding, narrative) in enumerate(
                    zip(verification.findings, narratives, strict=True)
                )
            ]
        )
