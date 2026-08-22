"""SQLite review-store repository tests."""

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
from veridoc.review.protocol import IdempotencyConflictError


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
