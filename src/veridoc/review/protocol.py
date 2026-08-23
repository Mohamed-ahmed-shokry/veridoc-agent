"""Read and write boundaries for the Phase 9 dedicated review store."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol, runtime_checkable

from veridoc.review.models import (
    ActorId,
    ActorRole,
    CaseAssignmentRequest,
    CaseDecisionRequest,
    CaseDetail,
    CaseEscalationRequest,
    CasePage,
    CaseStatus,
    IdempotentRequest,
    RequestId,
    ReviewSession,
    ReviewSnapshot,
)


class ReviewDataUnavailableError(RuntimeError):
    """Raised when review data cannot be read or written safely."""

    code = "review_data_unavailable"
    message = "Review data is not available on this server."

    def __init__(self) -> None:
        super().__init__(self.message)


class StaleVersionConflictError(RuntimeError):
    """Raised when a mutation's expected case version does not match current."""

    code = "review_case_version_conflict"
    message = "The case has changed since the expected version was read."

    def __init__(self) -> None:
        super().__init__(self.message)


class IdempotencyConflictError(RuntimeError):
    """Raised when an idempotency key is reused with a different request body."""

    code = "review_idempotency_conflict"
    message = "The idempotency key was already used with a different request."

    def __init__(self) -> None:
        super().__init__(self.message)


class ReviewAuthorizationError(RuntimeError):
    """Raised when an authenticated actor lacks authority for one operation."""

    code = "review_authorization_denied"
    message = "The actor is not authorized to perform this review operation."

    def __init__(self) -> None:
        super().__init__(self.message)


class ReassignmentReasonRequiredError(RuntimeError):
    """Raised when a case reassignment omits the required audit reason."""

    code = "review_reassignment_reason_required"
    message = "A reason is required when reassigning an already-assigned case."

    def __init__(self) -> None:
        super().__init__(self.message)


@runtime_checkable
class ReviewCaseReader(Protocol):
    """Read bounded case summaries and one case's full detail."""

    def list_cases(
        self,
        *,
        status: CaseStatus | None,
        assignee_id: ActorId | None,
        offset: int,
        limit: int,
    ) -> CasePage:
        """Return one bounded, filtered page of case summaries."""

    def get_case(self, case_id: str) -> CaseDetail | None:
        """Return one case's full snapshot, current state, and ordered events."""


@runtime_checkable
class ReviewCaseWriter(Protocol):
    """Create and transition review cases under version and idempotency guards."""

    def create_case(
        self,
        *,
        snapshot: ReviewSnapshot,
        creator_actor_id: ActorId,
        request_id: RequestId,
        idempotent_request: IdempotentRequest,
    ) -> CaseDetail:
        """Atomically create one case, its snapshot, and its creation event.

        A retry with the same idempotency key and request digest returns the
        original case; reuse with a different digest raises
        :class:`IdempotencyConflictError`.
        """

    def assign_case(
        self,
        case_id: str,
        *,
        request: CaseAssignmentRequest,
        actor_id: ActorId,
        actor_role: ActorRole,
        request_id: RequestId,
        idempotent_request: IdempotentRequest | None,
    ) -> CaseDetail | None:
        """Claim, assign, or reassign one case, appending its event atomically.

        Returns ``None`` when the case does not exist, raises
        :class:`ReviewAuthorizationError` when the actor's role and
        relationship to the case do not permit this operation, raises
        :class:`StaleVersionConflictError` when ``request.expected_version``
        does not match the current version, and raises
        :class:`IdempotencyConflictError` for an idempotency-key replay with a
        different request body.
        """

    def escalate_case(
        self,
        case_id: str,
        *,
        request: CaseEscalationRequest,
        actor_id: ActorId,
        actor_role: ActorRole,
        request_id: RequestId,
        idempotent_request: IdempotentRequest | None,
    ) -> CaseDetail | None:
        """Escalate one assigned case, appending its event atomically."""

    def decide_case(
        self,
        case_id: str,
        *,
        request: CaseDecisionRequest,
        actor_id: ActorId,
        actor_role: ActorRole,
        request_id: RequestId,
        idempotent_request: IdempotentRequest | None,
    ) -> CaseDetail | None:
        """Record one terminal decision, appending its event atomically."""


@runtime_checkable
class ReviewSessionStore(Protocol):
    """Create, resolve, and revoke hashed browser session records."""

    def create_session(
        self, *, session_digest: str, actor_id: ActorId, expires_at: datetime
    ) -> ReviewSession:
        """Persist one new session for an authenticated actor."""

    def resolve_session(self, session_digest: str) -> ReviewSession | None:
        """Return one session record by digest, or ``None`` when unknown.

        Callers must separately check whether the session is still active
        (unexpired and unrevoked); this lookup does not filter by state.
        """

    def revoke_session(self, session_digest: str) -> None:
        """Mark one session revoked; revoking an already-revoked session is a
        safe no-op.
        """
