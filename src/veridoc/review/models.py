"""Bounded actor, case, status, role, and decision identifier types."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

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


class ReviewModel(BaseModel):
    """Strict base model for untrusted or persisted review data."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )
