"""Typed domain models for Phase 9 review identifiers, snapshots, and events."""

from __future__ import annotations

import hashlib
from typing import Annotated, Literal, Self

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field, model_validator

from veridoc.processing.models import ProcessingResult

ActorRole = Literal["reviewer", "review_admin"]
CaseStatus = Literal["unassigned", "assigned", "escalated", "decided"]
DecisionValue = Literal["accept", "reject", "needs_correction"]
EventType = Literal[
    "case_created",
    "case_assigned",
    "case_reassigned",
    "case_escalated",
    "case_decided",
]

_IDENTIFIER_PATTERN = r"^[A-Za-z0-9][A-Za-z0-9._-]*$"
_ASSIGNMENT_EVENT_TYPES = frozenset({"case_assigned", "case_reassigned"})
_REASON_REQUIRED_EVENT_TYPES = frozenset(
    {"case_reassigned", "case_escalated", "case_decided"}
)

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
RequestId = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN),
]
IdempotencyKey = Annotated[
    str,
    Field(min_length=1, max_length=128, pattern=_IDENTIFIER_PATTERN),
]
EventMetadataValue = str | int | bool | None

REVIEW_SNAPSHOT_SCHEMA_VERSION = 1


class ReviewModel(BaseModel):
    """Strict base model for untrusted or persisted review data."""

    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        allow_inf_nan=False,
    )


def _model_digest(payload: BaseModel) -> str:
    return hashlib.sha256(payload.model_dump_json().encode("utf-8")).hexdigest()


def compute_content_digest(result: ProcessingResult) -> str:
    """Return the SHA-256 hex digest of one canonical processing-result JSON."""
    return _model_digest(result)


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


class ReviewEvent(ReviewModel):
    """One immutable, ordered audit event appended to a review case."""

    case_id: CaseId
    case_version: CaseVersion
    event_type: EventType
    actor_id: ActorId
    occurred_at: AwareDatetime
    request_id: RequestId
    idempotency_key: IdempotencyKey | None = None
    prior_status: CaseStatus | None = None
    resulting_status: CaseStatus
    reason: ReasonText | None = None
    decision: DecisionValue | None = None
    assigned_actor_id: ActorId | None = None
    metadata: dict[str, EventMetadataValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _verify_event_shape(self) -> Self:
        is_creation = self.event_type == "case_created"
        if is_creation and self.prior_status is not None:
            raise ValueError("case_created events must not record a prior status.")
        if not is_creation and self.prior_status is None:
            raise ValueError("Transition events must record a prior status.")

        is_decision = self.event_type == "case_decided"
        if is_decision and self.decision is None:
            raise ValueError("case_decided events must record a decision value.")
        if not is_decision and self.decision is not None:
            raise ValueError("Only case_decided events may record a decision value.")

        is_assignment = self.event_type in _ASSIGNMENT_EVENT_TYPES
        if is_assignment and self.assigned_actor_id is None:
            raise ValueError("Assignment events must record the assigned actor.")
        if not is_assignment and self.assigned_actor_id is not None:
            raise ValueError("Only assignment events may record an assigned actor.")

        if self.event_type in _REASON_REQUIRED_EVENT_TYPES and not self.reason:
            raise ValueError(f"{self.event_type} events must include a reason.")
        return self


MutationOperation = Literal[
    "create_case",
    "assign_case",
    "escalate_case",
    "decide_case",
]


class CaseAssignmentRequest(ReviewModel):
    """Request to claim (self), assign, or reassign a case to an actor."""

    expected_version: CaseVersion
    actor_id: ActorId | None = None


class CaseEscalationRequest(ReviewModel):
    """Request to escalate an assigned case with a required reason."""

    expected_version: CaseVersion
    reason: ReasonText


class CaseDecisionRequest(ReviewModel):
    """Request to record a terminal decision with a required reason."""

    expected_version: CaseVersion
    decision: DecisionValue
    reason: ReasonText


class IdempotentRequest(ReviewModel):
    """One idempotency-scoped mutation request identity."""

    actor_id: ActorId
    operation: MutationOperation
    idempotency_key: IdempotencyKey
    request_digest: str = Field(pattern=r"^[0-9a-f]{64}$")


def compute_request_digest(payload: BaseModel) -> str:
    """Return the SHA-256 hex digest of one canonical mutation request body."""
    return _model_digest(payload)


class CaseSummary(ReviewModel):
    """One bounded case-listing row without the snapshot or event history."""

    case_id: CaseId
    status: CaseStatus
    version: CaseVersion
    creator_actor_id: ActorId
    assignee_id: ActorId | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime


class CaseDetail(ReviewModel):
    """One case's immutable snapshot, current state, and ordered events."""

    case_id: CaseId
    status: CaseStatus
    version: CaseVersion
    creator_actor_id: ActorId
    assignee_id: ActorId | None = None
    created_at: AwareDatetime
    updated_at: AwareDatetime
    snapshot: ReviewSnapshot
    events: list[ReviewEvent] = Field(default_factory=list)


class CasePage(ReviewModel):
    """One bounded page of case summaries."""

    records: list[CaseSummary]
    offset: int = Field(ge=0)
    limit: int = Field(ge=1, le=200)
    total: int = Field(ge=0)
