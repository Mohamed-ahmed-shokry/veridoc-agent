"""Concurrency races for the dedicated review-store repository."""

from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from threading import Barrier

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.processing.models import ProcessingResult, ProcessingVerdict
from veridoc.review.models import (
    CaseAssignmentRequest,
    CaseDecisionRequest,
    IdempotentRequest,
    ReviewSnapshot,
    build_review_snapshot,
)
from veridoc.review.persistence.sqlite import SQLiteReviewRepository
from veridoc.review.protocol import (
    IdempotencyConflictError,
    ReviewAuthorizationError,
    StaleVersionConflictError,
)

_WORKERS = 8


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


def _repository(tmp_path: Path) -> SQLiteReviewRepository:
    repository = SQLiteReviewRepository(tmp_path / "review.sqlite")
    repository.initialize()
    return repository


def test_concurrent_create_case_with_the_same_key_yields_one_case(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    request = IdempotentRequest(
        actor_id="reviewer-1",
        operation="create_case",
        idempotency_key="race-key",
        request_digest="a" * 64,
    )
    ready = Barrier(_WORKERS)

    def create(index: int) -> str:
        ready.wait()
        case = repository.create_case(
            snapshot=_snapshot(),
            creator_actor_id="reviewer-1",
            request_id=f"request-{index}",
            idempotent_request=request,
        )
        return case.case_id

    with ThreadPoolExecutor(max_workers=_WORKERS) as executor:
        case_ids = list(executor.map(create, range(_WORKERS)))

    assert len(set(case_ids)) == 1
    page = repository.list_cases(status=None, assignee_id=None, offset=0, limit=200)
    assert page.total == 1


def test_concurrent_create_case_with_a_reused_key_and_different_digests_is_safe(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    ready = Barrier(_WORKERS)

    def create(index: int) -> str:
        ready.wait()
        try:
            case = repository.create_case(
                snapshot=_snapshot(),
                creator_actor_id="reviewer-1",
                request_id=f"request-{index}",
                idempotent_request=IdempotentRequest(
                    actor_id="reviewer-1",
                    operation="create_case",
                    idempotency_key="race-key",
                    request_digest=f"{index % 16:0>64}",
                ),
            )
            return f"ok:{case.case_id}"
        except IdempotencyConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=_WORKERS) as executor:
        outcomes = list(executor.map(create, range(_WORKERS)))

    successes = [outcome for outcome in outcomes if outcome.startswith("ok:")]
    assert len(successes) == 1
    page = repository.list_cases(status=None, assignee_id=None, offset=0, limit=200)
    assert page.total == 1


def test_concurrent_assign_case_with_the_same_expected_version_has_one_winner(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    case = repository.create_case(
        snapshot=_snapshot(),
        creator_actor_id="reviewer-1",
        request_id="request-create",
        idempotent_request=IdempotentRequest(
            actor_id="reviewer-1",
            operation="create_case",
            idempotency_key="create-key",
            request_digest="a" * 64,
        ),
    )
    ready = Barrier(_WORKERS)

    def claim(index: int) -> str:
        ready.wait()
        try:
            repository.assign_case(
                case.case_id,
                request=CaseAssignmentRequest(expected_version=1),
                actor_id=f"reviewer-{index}",
                actor_role="reviewer",
                request_id=f"request-assign-{index}",
                idempotent_request=None,
            )
            return "ok"
        except (StaleVersionConflictError, ReviewAuthorizationError):
            return "conflict"

    with ThreadPoolExecutor(max_workers=_WORKERS) as executor:
        outcomes = list(executor.map(claim, range(_WORKERS)))

    assert outcomes.count("ok") == 1
    updated = repository.get_case(case.case_id)
    assert updated is not None
    assert updated.status == "assigned"
    assert updated.version == 2
    assert [event.case_version for event in updated.events] == [1, 2]


def test_concurrent_decide_case_has_one_winner_and_a_consistent_event_chain(
    tmp_path: Path,
) -> None:
    repository = _repository(tmp_path)
    case = repository.create_case(
        snapshot=_snapshot(),
        creator_actor_id="reviewer-1",
        request_id="request-create",
        idempotent_request=IdempotentRequest(
            actor_id="reviewer-1",
            operation="create_case",
            idempotency_key="create-key",
            request_digest="a" * 64,
        ),
    )
    repository.assign_case(
        case.case_id,
        request=CaseAssignmentRequest(expected_version=1),
        actor_id="reviewer-2",
        actor_role="reviewer",
        request_id="request-assign",
        idempotent_request=None,
    )
    ready = Barrier(_WORKERS)

    def decide(index: int) -> str:
        ready.wait()
        try:
            repository.decide_case(
                case.case_id,
                request=CaseDecisionRequest(
                    expected_version=2, decision="accept", reason=f"Reason {index}."
                ),
                actor_id="reviewer-2",
                actor_role="reviewer",
                request_id=f"request-decide-{index}",
                idempotent_request=None,
            )
            return "ok"
        except StaleVersionConflictError:
            return "conflict"

    with ThreadPoolExecutor(max_workers=_WORKERS) as executor:
        outcomes = list(executor.map(decide, range(_WORKERS)))

    assert outcomes.count("ok") == 1
    updated = repository.get_case(case.case_id)
    assert updated is not None
    assert updated.status == "decided"
    assert updated.version == 3
    assert [event.case_version for event in updated.events] == [1, 2, 3]


@pytest.mark.parametrize("worker_count", [_WORKERS])
def test_concurrent_creates_with_distinct_keys_all_succeed_without_corruption(
    tmp_path: Path, worker_count: int
) -> None:
    repository = _repository(tmp_path)
    ready = Barrier(worker_count)

    def create(index: int) -> str:
        ready.wait()
        case = repository.create_case(
            snapshot=_snapshot(),
            creator_actor_id="reviewer-1",
            request_id=f"request-{index}",
            idempotent_request=IdempotentRequest(
                actor_id="reviewer-1",
                operation="create_case",
                idempotency_key=f"key-{index}",
                request_digest="a" * 64,
            ),
        )
        return case.case_id

    with ThreadPoolExecutor(max_workers=worker_count) as executor:
        case_ids = list(executor.map(create, range(worker_count)))

    assert len(set(case_ids)) == worker_count
    page = repository.list_cases(status=None, assignee_id=None, offset=0, limit=200)
    assert page.total == worker_count
    for case_id in case_ids:
        detail = repository.get_case(case_id)
        assert detail is not None
        assert [event.case_version for event in detail.events] == [1]
