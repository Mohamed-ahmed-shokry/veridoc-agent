"""SQLite review-store repository tests."""

import sqlite3
from pathlib import Path

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.processing.models import ProcessingResult, ProcessingVerdict
from veridoc.review.models import (
    IdempotentRequest,
    ReviewSnapshot,
    build_review_snapshot,
)
from veridoc.review.persistence.sqlite import SQLiteReviewRepository
from veridoc.review.protocol import IdempotencyConflictError, ReviewDataUnavailableError


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
