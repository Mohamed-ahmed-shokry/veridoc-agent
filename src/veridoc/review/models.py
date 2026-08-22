"""Typed domain models for Phase 9 review: identifiers and snapshots."""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from veridoc.processing.models import ProcessingResult

ActorRole = Literal["reviewer", "review_admin"]
CaseStatus = Literal["unassigned", "assigned", "escalated", "decided"]
DecisionValue = Literal["accept", "reject", "needs_correction"]

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"

ActorId = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN),
]
CaseId = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN),
]
CaseVersion = Annotated[int, Field(ge=1)]
ReasonText = Annotated[str, Field(min_length=1, max_length=2000)]

REVIEW_SNAPSHOT_SCHEMA_VERSION = 1


class ReviewModel(BaseModel):
    """Strict base model for untrusted or persisted review data."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


def compute_content_digest(result: ProcessingResult) -> str:
    """Return the SHA-256 hex digest of one canonical processing-result JSON."""
    return hashlib.sha256(result.model_dump_json().encode("utf-8")).hexdigest()


class ReviewSnapshot(ReviewModel):
    """One immutable, schema-versioned, digest-verified processing-result snapshot."""

    schema_version: int = Field(ge=1)
    content_digest: str = Field(pattern=r"^[0-9a-f]{64}$")
    result: ProcessingResult

    @model_validator(mode="after")
    def _verify_schema_version_and_digest(self) -> Self:
        if self.schema_version != REVIEW_SNAPSHOT_SCHEMA_VERSION:
            raise ValueError("Unsupported review snapshot schema version.")
        if self.content_digest != compute_content_digest(self.result):
            raise ValueError("Review snapshot content digest mismatch.")
        return self


def build_review_snapshot(result: ProcessingResult) -> ReviewSnapshot:
    """Build one schema-versioned, digest-verified snapshot for storage."""
    return ReviewSnapshot(
        schema_version=REVIEW_SNAPSHOT_SCHEMA_VERSION,
        content_digest=compute_content_digest(result),
        result=result,
    )


def hydrate_review_snapshot(raw_json: str | bytes) -> ReviewSnapshot:
    """Revalidate one persisted canonical snapshot against its schema and digest."""
    return ReviewSnapshot.model_validate_json(raw_json)
