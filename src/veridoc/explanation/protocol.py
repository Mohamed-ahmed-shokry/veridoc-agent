"""Provider-neutral boundary for explanation proposals."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field

from veridoc.verification.models import VerificationFinding, VerificationResult


@dataclass(frozen=True, slots=True)
class ExplanationRequest:
    """Verified findings supplied to an external explanation provider."""

    findings: tuple[VerificationFinding, ...]

    @classmethod
    def from_verification(cls, verification: VerificationResult) -> ExplanationRequest:
        """Create an immutable provider request from canonical findings."""
        return cls(findings=tuple(verification.findings))


class ExplanationDraft(BaseModel):
    """One provider-proposed narrative for a verified finding index."""

    model_config = ConfigDict(extra="forbid")

    finding_index: int = Field(ge=0)
    narrative: str = Field(min_length=1)


class ExplanationDraftResult(BaseModel):
    """All provider-proposed narratives for one explanation request."""

    model_config = ConfigDict(extra="forbid")

    drafts: list[ExplanationDraft] = Field(default_factory=list)


@runtime_checkable
class FindingExplainer(Protocol):
    """Produce text proposals from the deterministic verification evidence."""

    async def explain(self, request: ExplanationRequest) -> ExplanationDraftResult:
        """Return one proposed narrative for each supplied finding."""


class ExplanationUnavailableError(RuntimeError):
    """Raised when the configured explanation provider cannot be used safely."""

    def __init__(self) -> None:
        super().__init__("Evidence-grounded explanation is not available.")


class ExplanationProcessingError(RuntimeError):
    """Raised when a provider response cannot be used as an explanation draft."""

    def __init__(self) -> None:
        super().__init__("The explanation provider did not return a valid draft.")
