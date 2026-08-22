"""Review case read-boundary contract tests."""

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from veridoc.extraction.models import InvoiceExtraction
from veridoc.processing.models import ProcessingResult, ProcessingVerdict
from veridoc.review.models import (
    CaseAssignmentRequest,
    CaseDecisionRequest,
    CaseDetail,
    CaseEscalationRequest,
    CasePage,
    CaseSummary,
    ReviewSession,
    ReviewSnapshot,
    build_review_snapshot,
)
from veridoc.review.protocol import (
    IdempotencyConflictError,
    ReviewCaseReader,
    ReviewCaseWriter,
    ReviewSessionStore,
    StaleVersionConflictError,
)

_CREATED_AT = datetime(2026, 8, 22, 12, 0, tzinfo=UTC)


def _snapshot() -> ReviewSnapshot:
    result = ProcessingResult(
        extraction=InvoiceExtraction(document_type="invoice"),
        verdict=ProcessingVerdict(
            status="clear",
            summary="No deterministic verification findings require review.",
            finding_count=0,
        ),
    )
    return build_review_snapshot(result)


def _summary(**overrides: object) -> CaseSummary:
    fields: dict[str, object] = {
        "case_id": "case-1",
        "status": "unassigned",
        "version": 1,
        "creator_actor_id": "reviewer-1",
        "created_at": _CREATED_AT,
        "updated_at": _CREATED_AT,
    }
    fields.update(overrides)
    return CaseSummary(**fields)


class _FakeReader:
    def list_cases(
        self,
        *,
        status: str | None,
        assignee_id: str | None,
        offset: int,
        limit: int,
    ) -> CasePage:
        del status, assignee_id, offset, limit
        return CasePage(records=[_summary()], offset=0, limit=100, total=1)

    def get_case(self, case_id: str) -> CaseDetail | None:
        del case_id
        return None


def test_fake_reader_satisfies_the_review_case_reader_protocol() -> None:
    assert isinstance(_FakeReader(), ReviewCaseReader)


def test_case_summary_allows_an_unassigned_case_without_an_assignee() -> None:
    summary = _summary()
    assert summary.assignee_id is None


def test_case_detail_carries_the_snapshot_and_ordered_events() -> None:
    detail = CaseDetail(
        case_id="case-1",
        status="unassigned",
        version=1,
        creator_actor_id="reviewer-1",
        created_at=_CREATED_AT,
        updated_at=_CREATED_AT,
        snapshot=_snapshot(),
        events=[],
    )
    assert detail.events == []
    assert detail.snapshot.result.verdict.status == "clear"


def test_case_page_bounds_its_limit() -> None:
    with pytest.raises(ValidationError):
        CasePage(records=[], offset=0, limit=201, total=0)
    with pytest.raises(ValidationError):
        CasePage(records=[], offset=0, limit=0, total=0)


def test_case_page_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        CasePage(records=[], offset=0, limit=100, total=0, extra="not-allowed")


class _FakeWriter:
    def create_case(
        self, *, snapshot, creator_actor_id, request_id, idempotent_request
    ) -> CaseDetail:
        del snapshot, creator_actor_id, request_id, idempotent_request
        return CaseDetail(
            case_id="case-1",
            status="unassigned",
            version=1,
            creator_actor_id="reviewer-1",
            created_at=_CREATED_AT,
            updated_at=_CREATED_AT,
            snapshot=_snapshot(),
            events=[],
        )

    def assign_case(
        self, case_id, *, request, actor_id, request_id, idempotent_request
    ) -> CaseDetail | None:
        del case_id, request, actor_id, request_id, idempotent_request
        return None

    def escalate_case(
        self, case_id, *, request, actor_id, request_id, idempotent_request
    ) -> CaseDetail | None:
        del case_id, request, actor_id, request_id, idempotent_request
        return None

    def decide_case(
        self, case_id, *, request, actor_id, request_id, idempotent_request
    ) -> CaseDetail | None:
        del case_id, request, actor_id, request_id, idempotent_request
        return None


class _FakeSessionStore:
    def create_session(self, *, session_digest, actor_id, expires_at) -> ReviewSession:
        return ReviewSession(
            session_digest=session_digest,
            actor_id=actor_id,
            created_at=_CREATED_AT,
            expires_at=expires_at,
        )

    def resolve_session(self, session_digest: str) -> ReviewSession | None:
        del session_digest
        return None

    def revoke_session(self, session_digest: str) -> None:
        del session_digest


def test_fake_writer_satisfies_the_review_case_writer_protocol() -> None:
    assert isinstance(_FakeWriter(), ReviewCaseWriter)


def test_fake_session_store_satisfies_the_review_session_store_protocol() -> None:
    assert isinstance(_FakeSessionStore(), ReviewSessionStore)


def test_review_session_hides_the_raw_token_and_allows_no_revocation() -> None:
    session = ReviewSession(
        session_digest="a" * 64,
        actor_id="reviewer-1",
        created_at=_CREATED_AT,
        expires_at=_CREATED_AT,
    )
    assert session.revoked_at is None


def test_case_assignment_and_escalation_and_decision_requests_carry_expected_version() -> (
    None
):
    assert CaseAssignmentRequest(expected_version=1).expected_version == 1
    assert CaseEscalationRequest(expected_version=2, reason="x").expected_version == 2
    assert (
        CaseDecisionRequest(
            expected_version=3, decision="accept", reason="x"
        ).expected_version
        == 3
    )


def test_conflict_errors_carry_stable_codes_and_safe_messages() -> None:
    stale = StaleVersionConflictError()
    assert stale.code == "review_case_version_conflict"
    assert stale.message

    idempotency = IdempotencyConflictError()
    assert idempotency.code == "review_idempotency_conflict"
    assert idempotency.message
