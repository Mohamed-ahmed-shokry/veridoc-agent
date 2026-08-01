"""Typed outputs for explanations derived from verified findings."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from veridoc.verification.models import VerificationFinding

ExplanationSource = Literal["deterministic", "llm"]


class FindingExplanation(BaseModel):
    """One explanation paired with the immutable finding it describes."""

    model_config = ConfigDict(extra="forbid")

    finding: VerificationFinding
    narrative: str = Field(min_length=1)
    numerical_context: str = Field(min_length=1)
    source: ExplanationSource


class ExplanationResult(BaseModel):
    """Evidence-grounded explanations for all verification findings."""

    model_config = ConfigDict(extra="forbid")

    explanations: list[FindingExplanation] = Field(default_factory=list)
