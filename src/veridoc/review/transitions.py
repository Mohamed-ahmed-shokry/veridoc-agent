"""Deterministic Phase 9 case state transition rules."""

from __future__ import annotations

from dataclasses import dataclass

from veridoc.review.models import CaseStatus, EventType, MutationOperation


class InvalidTransitionError(ValueError):
    """Raised when an operation is not allowed from the case's current status."""


@dataclass(frozen=True, slots=True)
class Transition:
    """One allowed operation outcome: the event type and the resulting status."""

    event_type: EventType
    resulting_status: CaseStatus


_ALLOWED_TRANSITIONS: dict[tuple[CaseStatus | None, MutationOperation], Transition] = {
    (None, "create_case"): Transition("case_created", "unassigned"),
    ("unassigned", "assign_case"): Transition("case_assigned", "assigned"),
    ("escalated", "assign_case"): Transition("case_assigned", "assigned"),
    ("assigned", "assign_case"): Transition("case_reassigned", "assigned"),
    ("assigned", "escalate_case"): Transition("case_escalated", "escalated"),
    ("assigned", "decide_case"): Transition("case_decided", "decided"),
}


def next_transition(
    current_status: CaseStatus | None, operation: MutationOperation
) -> Transition:
    """Return the allowed transition for one operation, or raise if forbidden."""
    transition = _ALLOWED_TRANSITIONS.get((current_status, operation))
    if transition is None:
        raise InvalidTransitionError(
            f"Operation {operation!r} is not allowed from status {current_status!r}."
        )
    return transition


def is_terminal(status: CaseStatus) -> bool:
    """Return whether a case status accepts no further transitions."""
    return status == "decided"
