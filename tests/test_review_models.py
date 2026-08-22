"""Validation tests for bounded review identifier, role, and status types."""

import pytest
from pydantic import TypeAdapter, ValidationError

from veridoc.extraction.models import InvoiceExtraction
from veridoc.processing.models import ProcessingResult, ProcessingVerdict
from veridoc.review.models import (
    REVIEW_SNAPSHOT_SCHEMA_VERSION,
    ActorId,
    ActorRole,
    CaseId,
    CaseStatus,
    CaseVersion,
    DecisionValue,
    ReasonText,
    ReviewModel,
    ReviewSnapshot,
    build_review_snapshot,
    compute_content_digest,
    hydrate_review_snapshot,
)


def _processing_result() -> ProcessingResult:
    return ProcessingResult(
        extraction=InvoiceExtraction(document_type="invoice", vendor_name="Fictional"),
        verdict=ProcessingVerdict(
            status="clear",
            summary="No deterministic verification findings require review.",
            finding_count=0,
        ),
    )


_actor_id = TypeAdapter(ActorId)
_case_id = TypeAdapter(CaseId)
_case_version = TypeAdapter(CaseVersion)
_reason_text = TypeAdapter(ReasonText)
_actor_role = TypeAdapter(ActorRole)
_case_status = TypeAdapter(CaseStatus)
_decision_value = TypeAdapter(DecisionValue)


@pytest.mark.parametrize("adapter", [_actor_id, _case_id])
def test_identifiers_accept_bounded_safe_values(adapter: TypeAdapter[str]) -> None:
    assert adapter.validate_python("reviewer-1") == "reviewer-1"
    assert adapter.validate_python("a" * 128) == "a" * 128


@pytest.mark.parametrize("adapter", [_actor_id, _case_id])
@pytest.mark.parametrize(
    "value",
    ["", "a" * 129, "-leading-hyphen", "has space", "has/slash", "has\nnewline"],
)
def test_identifiers_reject_unsafe_or_oversized_values(
    adapter: TypeAdapter[str], value: str
) -> None:
    with pytest.raises(ValidationError):
        adapter.validate_python(value)


def test_case_version_requires_a_positive_integer() -> None:
    assert _case_version.validate_python(1) == 1

    with pytest.raises(ValidationError):
        _case_version.validate_python(0)
    with pytest.raises(ValidationError):
        _case_version.validate_python(-1)


def test_reason_text_requires_nonblank_bounded_content() -> None:
    assert _reason_text.validate_python("Escalating for manager review.")

    with pytest.raises(ValidationError):
        _reason_text.validate_python("")
    with pytest.raises(ValidationError):
        _reason_text.validate_python("x" * 2001)


def test_actor_role_allows_only_reviewer_and_review_admin() -> None:
    assert _actor_role.validate_python("reviewer") == "reviewer"
    assert _actor_role.validate_python("review_admin") == "review_admin"
    with pytest.raises(ValidationError):
        _actor_role.validate_python("owner")


def test_case_status_allows_only_the_four_defined_states() -> None:
    for status in ("unassigned", "assigned", "escalated", "decided"):
        assert _case_status.validate_python(status) == status
    with pytest.raises(ValidationError):
        _case_status.validate_python("archived")


def test_decision_value_allows_only_the_three_defined_outcomes() -> None:
    for decision in ("accept", "reject", "needs_correction"):
        assert _decision_value.validate_python(decision) == decision
    with pytest.raises(ValidationError):
        _decision_value.validate_python("approved")


def test_build_review_snapshot_matches_the_current_schema_version() -> None:
    snapshot = build_review_snapshot(_processing_result())

    assert snapshot.schema_version == REVIEW_SNAPSHOT_SCHEMA_VERSION
    assert snapshot.content_digest == compute_content_digest(snapshot.result)
    assert len(snapshot.content_digest) == 64


def test_build_review_snapshot_is_deterministic_for_equal_results() -> None:
    first = build_review_snapshot(_processing_result())
    second = build_review_snapshot(_processing_result())

    assert first.content_digest == second.content_digest


def test_hydrate_review_snapshot_round_trips_through_json() -> None:
    snapshot = build_review_snapshot(_processing_result())

    hydrated = hydrate_review_snapshot(snapshot.model_dump_json())

    assert hydrated == snapshot


def test_review_snapshot_rejects_a_tampered_digest() -> None:
    snapshot = build_review_snapshot(_processing_result())

    with pytest.raises(ValidationError):
        ReviewSnapshot.model_validate(
            {**snapshot.model_dump(mode="json"), "content_digest": "0" * 64}
        )


def test_review_snapshot_rejects_an_unsupported_schema_version() -> None:
    snapshot = build_review_snapshot(_processing_result())

    with pytest.raises(ValidationError):
        ReviewSnapshot.model_validate(
            {**snapshot.model_dump(mode="json"), "schema_version": 2}
        )


def test_review_model_forbids_extra_fields_and_strips_strings() -> None:
    class _Probe(ReviewModel):
        actor_id: ActorId

    probe = _Probe(actor_id="  reviewer-1  ")
    assert probe.actor_id == "reviewer-1"

    with pytest.raises(ValidationError):
        _Probe(actor_id="reviewer-1", extra="not-allowed")
