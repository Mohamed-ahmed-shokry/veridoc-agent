"""Exhaustive coverage of the Phase 9 case transition policy."""

import pytest

from veridoc.review.models import CaseStatus, MutationOperation
from veridoc.review.transitions import (
    InvalidTransitionError,
    is_terminal,
    next_transition,
)

_ALL_STATUSES: tuple[CaseStatus | None, ...] = (
    None,
    "unassigned",
    "assigned",
    "escalated",
    "decided",
)
_ALL_OPERATIONS: tuple[MutationOperation, ...] = (
    "create_case",
    "assign_case",
    "escalate_case",
    "decide_case",
)
_ALLOWED = {
    (None, "create_case"): ("case_created", "unassigned"),
    ("unassigned", "assign_case"): ("case_assigned", "assigned"),
    ("escalated", "assign_case"): ("case_assigned", "assigned"),
    ("assigned", "assign_case"): ("case_reassigned", "assigned"),
    ("assigned", "escalate_case"): ("case_escalated", "escalated"),
    ("assigned", "decide_case"): ("case_decided", "decided"),
}


@pytest.mark.parametrize("current_status", _ALL_STATUSES)
@pytest.mark.parametrize("operation", _ALL_OPERATIONS)
def test_every_status_operation_pair_matches_the_documented_table(
    current_status: CaseStatus | None, operation: MutationOperation
) -> None:
    key = (current_status, operation)
    if key in _ALLOWED:
        expected_event_type, expected_status = _ALLOWED[key]
        transition = next_transition(current_status, operation)
        assert transition.event_type == expected_event_type
        assert transition.resulting_status == expected_status
    else:
        with pytest.raises(InvalidTransitionError):
            next_transition(current_status, operation)


def test_exactly_six_transitions_are_allowed() -> None:
    allowed = [
        (status, operation)
        for status in _ALL_STATUSES
        for operation in _ALL_OPERATIONS
        if (status, operation) in _ALLOWED
    ]
    assert len(allowed) == 6


def test_only_decided_is_terminal() -> None:
    assert is_terminal("decided") is True
    for status in ("unassigned", "assigned", "escalated"):
        assert is_terminal(status) is False
