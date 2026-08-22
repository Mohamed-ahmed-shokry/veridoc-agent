"""Validation tests for bounded review identifier, role, and status types."""

import pytest
from pydantic import TypeAdapter, ValidationError

from veridoc.review.models import (
    ActorId,
    ActorRole,
    CaseId,
    CaseStatus,
    CaseVersion,
    DecisionValue,
    ReasonText,
    ReviewModel,
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


def test_review_model_forbids_extra_fields_and_strips_strings() -> None:
    class _Probe(ReviewModel):
        actor_id: ActorId

    probe = _Probe(actor_id="  reviewer-1  ")
    assert probe.actor_id == "reviewer-1"

    with pytest.raises(ValidationError):
        _Probe(actor_id="reviewer-1", extra="not-allowed")
