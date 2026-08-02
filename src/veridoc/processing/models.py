"""Typed final values returned after complete invoice processing."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from veridoc.explanation.models import FindingExplanation
from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import FindingSeverity, VerificationFinding

VerdictStatus = Literal["clear", "review_required"]


class ProcessingVerdict(BaseModel):
    """Deterministic delivery status derived from verification findings."""

    model_config = ConfigDict(extra="forbid")

    status: VerdictStatus
    summary: str = Field(min_length=1)
    finding_count: int = Field(ge=0)
    highest_severity: FindingSeverity | None = None


class ProcessingResult(BaseModel):
    """Typed extraction, evidence, findings, explanations, and final verdict."""

    model_config = ConfigDict(extra="forbid")

    extraction: InvoiceExtraction
    findings: list[VerificationFinding] = Field(default_factory=list)
    explanations: list[FindingExplanation] = Field(default_factory=list)
    verdict: ProcessingVerdict
