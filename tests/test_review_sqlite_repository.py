"""SQLite review-store repository tests."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.processing.models import ProcessingResult, ProcessingVerdict
from veridoc.review.models import (
    CaseAssignmentRequest,
    CaseDecisionRequest,
    CaseDetail,
    CaseEscalationRequest,
    IdempotentRequest,
    ReviewSnapshot,
    build_review_snapshot,
)
from veridoc.review.persistence.sqlite import SQLiteReviewRepository
from veridoc.review.protocol import (
    IdempotencyConflictError,
    ReviewAuthorizationError,
    ReviewDataUnavailableError,
    StaleVersionConflictError,
)


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


def _idempotent_request(
    *, idempotency_key: str = "key-1", request_digest: str = "a" * 64
) -> IdempotentRequest:
    return IdempotentRequest(
        actor_id="reviewer-1",
        operation="create_case",
        idempotency_key=idempotency_key,
        request_digest=request_digest,
    )


def _repository(tmp_path: Path) -> SQLiteReviewRepository:
    repository = SQLiteReviewRepository(tmp_path / "review.sqlite")
    repository.initialize()
    return repository


def test_create_case_stores_the_snapshot_and_initial_event(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    case = repository.create_case(
        snapshot=_snapshot(),
        creator_actor_id="reviewer-1",
        request_id="request-1",
        idempotent_request=_idempotent_request(),
    )

    assert case.status == "unassigned"
    assert case.version == 1
    assert case.assignee_id is None
    assert case.creator_actor_id == "reviewer-1"
    assert len(case.events) == 1
    assert case.events[0].event_type == "case_created"
    assert case.events[0].request_id == "request-1"
    assert case.snapshot.result.verdict.status == "clear"


def test_create_case_is_idempotent_for_a_repeated_key_and_digest(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    request = _idempotent_request()

    first = repository.create_case(
        snapshot=_snapshot(),
        creator_actor_id="reviewer-1",
        request_id="request-1",
        idempotent_request=request,
    )
    second = repository.create_case(
        snapshot=_snapshot(),
        creator_actor_id="reviewer-1",
        request_id="request-2",
        idempotent_request=request,
    )

    assert first.case_id == second.case_id
    assert len(second.events) == 1


def test_create_case_rejects_a_reused_key_with_a_different_digest(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    repository.create_case(
        snapshot=_snapshot(),
        creator_actor_id="reviewer-1",
        request_id="request-1",
        idempotent_request=_idempotent_request(),
    )

    with pytest.raises(IdempotencyConflictError):
        repository.create_case(
            snapshot=_snapshot(),
            creator_actor_id="reviewer-1",
            request_id="request-2",
            idempotent_request=_idempotent_request(request_digest="b" * 64),
        )


def test_create_case_allows_distinct_cases_for_distinct_keys(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    first = repository.create_case(
        snapshot=_snapshot(),
        creator_actor_id="reviewer-1",
        request_id="request-1",
        idempotent_request=_idempotent_request(idempotency_key="key-1"),
    )
    second = repository.create_case(
        snapshot=_snapshot(),
        creator_actor_id="reviewer-1",
        request_id="request-2",
        idempotent_request=_idempotent_request(idempotency_key="key-2"),
    )

    assert first.case_id != second.case_id


def test_get_case_returns_the_stored_snapshot_and_events(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    created = repository.create_case(
        snapshot=_snapshot(),
        creator_actor_id="reviewer-1",
        request_id="request-1",
        idempotent_request=_idempotent_request(),
    )

    fetched = repository.get_case(created.case_id)

    assert fetched is not None
    assert fetched.case_id == created.case_id
    assert fetched.snapshot == created.snapshot
    assert [event.event_type for event in fetched.events] == ["case_created"]


def test_get_case_returns_none_for_an_unknown_case(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    assert repository.get_case("unknown-case") is None


def test_get_case_rejects_a_tampered_snapshot_digest(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    created = repository.create_case(
        snapshot=_snapshot(),
        creator_actor_id="reviewer-1",
        request_id="request-1",
        idempotent_request=_idempotent_request(),
    )

    with sqlite3.connect(tmp_path / "review.sqlite") as connection:
        connection.execute(
            "UPDATE review_cases SET snapshot_digest = ? WHERE case_id = ?",
            ("0" * 64, created.case_id),
        )
        connection.commit()

    with pytest.raises(ReviewDataUnavailableError):
        repository.get_case(created.case_id)


def _create_cases(repository: SQLiteReviewRepository, count: int) -> list[str]:
    return [
        repository.create_case(
            snapshot=_snapshot(),
            creator_actor_id="reviewer-1",
            request_id=f"request-{index}",
            idempotent_request=_idempotent_request(idempotency_key=f"key-{index}"),
        ).case_id
        for index in range(count)
    ]


def test_list_cases_returns_pages_in_stable_creation_order(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case_ids = _create_cases(repository, 3)

    page = repository.list_cases(status=None, assignee_id=None, offset=0, limit=200)

    assert page.total == 3
    assert [record.case_id for record in page.records] == case_ids


def test_list_cases_bounds_offset_and_limit(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case_ids = _create_cases(repository, 3)

    page = repository.list_cases(status=None, assignee_id=None, offset=1, limit=1)

    assert page.total == 3
    assert page.offset == 1
    assert page.limit == 1
    assert [record.case_id for record in page.records] == [case_ids[1]]


def test_list_cases_filters_by_status(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    _create_cases(repository, 2)

    unassigned_page = repository.list_cases(
        status="unassigned", assignee_id=None, offset=0, limit=200
    )
    decided_page = repository.list_cases(
        status="decided", assignee_id=None, offset=0, limit=200
    )

    assert unassigned_page.total == 2
    assert decided_page.total == 0


def test_list_cases_filters_by_assignee_id(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case_ids = _create_cases(repository, 2)

    with sqlite3.connect(tmp_path / "review.sqlite") as connection:
        connection.execute(
            "UPDATE review_cases SET assignee_id = 'reviewer-2' WHERE case_id = ?",
            (case_ids[0],),
        )
        connection.commit()

    assigned_page = repository.list_cases(
        status=None, assignee_id="reviewer-2", offset=0, limit=200
    )
    unassigned_filter_page = repository.list_cases(
        status=None, assignee_id="reviewer-3", offset=0, limit=200
    )

    assert [record.case_id for record in assigned_page.records] == [case_ids[0]]
    assert unassigned_filter_page.total == 0


def _create_case(
    repository: SQLiteReviewRepository, *, key: str = "create-key"
) -> CaseDetail:
    return repository.create_case(
        snapshot=_snapshot(),
        creator_actor_id="reviewer-1",
        request_id="request-create",
        idempotent_request=_idempotent_request(idempotency_key=key),
    )


def test_assign_case_self_claim_by_a_reviewer(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)

    updated = repository.assign_case(
        case.case_id,
        request=CaseAssignmentRequest(expected_version=1),
        actor_id="reviewer-2",
        actor_role="reviewer",
        request_id="request-assign",
        idempotent_request=None,
    )

    assert updated is not None
    assert updated.status == "assigned"
    assert updated.version == 2
    assert updated.assignee_id == "reviewer-2"
    assert updated.events[-1].event_type == "case_assigned"
    assert updated.events[-1].assigned_actor_id == "reviewer-2"


def test_assign_case_by_review_admin_to_another_actor(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)

    updated = repository.assign_case(
        case.case_id,
        request=CaseAssignmentRequest(expected_version=1, actor_id="reviewer-2"),
        actor_id="admin-1",
        actor_role="review_admin",
        request_id="request-assign",
        idempotent_request=None,
    )

    assert updated is not None
    assert updated.assignee_id == "reviewer-2"


def test_assign_case_rejects_a_reviewer_assigning_someone_else(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)

    with pytest.raises(ReviewAuthorizationError):
        repository.assign_case(
            case.case_id,
            request=CaseAssignmentRequest(expected_version=1, actor_id="reviewer-3"),
            actor_id="reviewer-2",
            actor_role="reviewer",
            request_id="request-assign",
            idempotent_request=None,
        )


def test_assign_case_rejects_reassignment_by_a_reviewer(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)
    repository.assign_case(
        case.case_id,
        request=CaseAssignmentRequest(expected_version=1),
        actor_id="reviewer-2",
        actor_role="reviewer",
        request_id="request-assign",
        idempotent_request=None,
    )

    with pytest.raises(ReviewAuthorizationError):
        repository.assign_case(
            case.case_id,
            request=CaseAssignmentRequest(expected_version=2, actor_id="reviewer-3"),
            actor_id="reviewer-2",
            actor_role="reviewer",
            request_id="request-reassign",
            idempotent_request=None,
        )


def test_assign_case_rejects_a_stale_expected_version(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)
    repository.assign_case(
        case.case_id,
        request=CaseAssignmentRequest(expected_version=1),
        actor_id="reviewer-2",
        actor_role="reviewer",
        request_id="request-assign",
        idempotent_request=None,
    )

    with pytest.raises(StaleVersionConflictError):
        repository.assign_case(
            case.case_id,
            request=CaseAssignmentRequest(expected_version=1, actor_id="reviewer-2"),
            actor_id="admin-1",
            actor_role="review_admin",
            request_id="request-retry",
            idempotent_request=None,
        )


def test_assign_case_returns_none_for_an_unknown_case(tmp_path: Path) -> None:
    repository = _repository(tmp_path)

    result = repository.assign_case(
        "unknown-case",
        request=CaseAssignmentRequest(expected_version=1),
        actor_id="reviewer-1",
        actor_role="reviewer",
        request_id="request-1",
        idempotent_request=None,
    )

    assert result is None


def test_assign_case_is_idempotent_for_a_repeated_key(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)
    request = _idempotent_request(idempotency_key="assign-key")

    first = repository.assign_case(
        case.case_id,
        request=CaseAssignmentRequest(expected_version=1),
        actor_id="reviewer-2",
        actor_role="reviewer",
        request_id="request-1",
        idempotent_request=request,
    )
    second = repository.assign_case(
        case.case_id,
        request=CaseAssignmentRequest(expected_version=1),
        actor_id="reviewer-2",
        actor_role="reviewer",
        request_id="request-2",
        idempotent_request=request,
    )

    assert first == second


def _assign_case(
    repository: SQLiteReviewRepository, case_id: str, *, actor_id: str = "reviewer-2"
) -> CaseDetail | None:
    return repository.assign_case(
        case_id,
        request=CaseAssignmentRequest(expected_version=1),
        actor_id=actor_id,
        actor_role="reviewer",
        request_id="request-assign",
        idempotent_request=None,
    )


def test_escalate_case_by_the_assignee(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)
    _assign_case(repository, case.case_id)

    updated = repository.escalate_case(
        case.case_id,
        request=CaseEscalationRequest(expected_version=2, reason="Cannot decide."),
        actor_id="reviewer-2",
        actor_role="reviewer",
        request_id="request-escalate",
        idempotent_request=None,
    )

    assert updated is not None
    assert updated.status == "escalated"
    assert updated.version == 3
    assert updated.assignee_id == "reviewer-2"
    assert updated.events[-1].event_type == "case_escalated"
    assert updated.events[-1].reason == "Cannot decide."


def test_escalate_case_by_review_admin_who_is_not_the_assignee(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)
    _assign_case(repository, case.case_id)

    updated = repository.escalate_case(
        case.case_id,
        request=CaseEscalationRequest(expected_version=2, reason="Needs review."),
        actor_id="admin-1",
        actor_role="review_admin",
        request_id="request-escalate",
        idempotent_request=None,
    )

    assert updated is not None
    assert updated.status == "escalated"


def test_escalate_case_rejects_a_non_assignee_reviewer(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)
    _assign_case(repository, case.case_id)

    with pytest.raises(ReviewAuthorizationError):
        repository.escalate_case(
            case.case_id,
            request=CaseEscalationRequest(expected_version=2, reason="Not mine."),
            actor_id="reviewer-3",
            actor_role="reviewer",
            request_id="request-escalate",
            idempotent_request=None,
        )


def test_escalate_case_rejects_an_unassigned_case(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)

    with pytest.raises(StaleVersionConflictError):
        repository.escalate_case(
            case.case_id,
            request=CaseEscalationRequest(expected_version=1, reason="Too soon."),
            actor_id="reviewer-1",
            actor_role="review_admin",
            request_id="request-escalate",
            idempotent_request=None,
        )


def test_decide_case_by_the_assignee_is_terminal(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)
    _assign_case(repository, case.case_id)

    updated = repository.decide_case(
        case.case_id,
        request=CaseDecisionRequest(
            expected_version=2, decision="accept", reason="Amounts reconcile."
        ),
        actor_id="reviewer-2",
        actor_role="reviewer",
        request_id="request-decide",
        idempotent_request=None,
    )

    assert updated is not None
    assert updated.status == "decided"
    assert updated.version == 3
    assert updated.events[-1].event_type == "case_decided"
    assert updated.events[-1].decision == "accept"
    assert updated.events[-1].reason == "Amounts reconcile."


def test_decide_case_by_review_admin_who_is_not_the_assignee(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)
    _assign_case(repository, case.case_id)

    updated = repository.decide_case(
        case.case_id,
        request=CaseDecisionRequest(
            expected_version=2, decision="reject", reason="Mismatch."
        ),
        actor_id="admin-1",
        actor_role="review_admin",
        request_id="request-decide",
        idempotent_request=None,
    )

    assert updated is not None
    assert updated.status == "decided"


def test_decide_case_rejects_a_non_assignee_reviewer(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)
    _assign_case(repository, case.case_id)

    with pytest.raises(ReviewAuthorizationError):
        repository.decide_case(
            case.case_id,
            request=CaseDecisionRequest(
                expected_version=2, decision="accept", reason="Not mine."
            ),
            actor_id="reviewer-3",
            actor_role="reviewer",
            request_id="request-decide",
            idempotent_request=None,
        )


def test_decide_case_is_terminal_and_rejects_a_second_decision(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)
    _assign_case(repository, case.case_id)
    repository.decide_case(
        case.case_id,
        request=CaseDecisionRequest(
            expected_version=2, decision="accept", reason="Amounts reconcile."
        ),
        actor_id="reviewer-2",
        actor_role="reviewer",
        request_id="request-decide",
        idempotent_request=None,
    )

    with pytest.raises(StaleVersionConflictError):
        repository.decide_case(
            case.case_id,
            request=CaseDecisionRequest(
                expected_version=3, decision="reject", reason="Changed my mind."
            ),
            actor_id="reviewer-2",
            actor_role="reviewer",
            request_id="request-redecide",
            idempotent_request=None,
        )


def test_decide_case_rejects_deciding_an_unassigned_case(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    case = _create_case(repository)

    with pytest.raises(StaleVersionConflictError):
        repository.decide_case(
            case.case_id,
            request=CaseDecisionRequest(
                expected_version=1, decision="accept", reason="Too soon."
            ),
            actor_id="reviewer-1",
            actor_role="review_admin",
            request_id="request-decide",
            idempotent_request=None,
        )


def test_create_session_persists_the_hashed_digest_only(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    expires_at = datetime(2026, 8, 23, 0, 0, tzinfo=UTC)

    session = repository.create_session(
        session_digest="a" * 64, actor_id="reviewer-1", expires_at=expires_at
    )

    assert session.session_digest == "a" * 64
    assert session.actor_id == "reviewer-1"
    assert session.revoked_at is None

    with sqlite3.connect(tmp_path / "review.sqlite") as connection:
        columns = {
            row[0]
            for row in connection.execute("SELECT * FROM review_sessions").description
        }
    assert "raw_token" not in columns


def test_resolve_session_returns_the_stored_record(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    expires_at = datetime(2026, 8, 23, 0, 0, tzinfo=UTC)
    repository.create_session(
        session_digest="a" * 64, actor_id="reviewer-1", expires_at=expires_at
    )

    resolved = repository.resolve_session("a" * 64)

    assert resolved is not None
    assert resolved.actor_id == "reviewer-1"


def test_resolve_session_returns_none_for_an_unknown_digest(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    assert repository.resolve_session("f" * 64) is None


def test_revoke_session_sets_revoked_at_once(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    expires_at = datetime(2026, 8, 23, 0, 0, tzinfo=UTC)
    repository.create_session(
        session_digest="a" * 64, actor_id="reviewer-1", expires_at=expires_at
    )

    repository.revoke_session("a" * 64)
    first_revocation = repository.resolve_session("a" * 64)
    assert first_revocation is not None
    assert first_revocation.revoked_at is not None

    repository.revoke_session("a" * 64)
    second_revocation = repository.resolve_session("a" * 64)

    assert second_revocation is not None
    assert second_revocation.revoked_at == first_revocation.revoked_at


def test_revoke_session_is_a_safe_no_op_for_an_unknown_digest(tmp_path: Path) -> None:
    repository = _repository(tmp_path)
    repository.revoke_session("f" * 64)
