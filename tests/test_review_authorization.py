"""Complete permission matrix coverage for the Phase 9 authorization policy."""

import pytest

from veridoc.review.models import ActorRole, CaseStatus, MutationOperation
from veridoc.review.transitions import authorize_operation

_ACTOR = "reviewer-1"
_OTHER_ACTOR = "reviewer-2"
_STATUSES: tuple[CaseStatus | None, ...] = (
    None,
    "unassigned",
    "assigned",
    "escalated",
    "decided",
)
_OPERATIONS: tuple[MutationOperation, ...] = (
    "create_case",
    "assign_case",
    "escalate_case",
    "decide_case",
)
_ROLES: tuple[ActorRole, ...] = ("reviewer", "review_admin")


def _expected(
    role: ActorRole,
    operation: MutationOperation,
    status: CaseStatus | None,
    assignee_is_actor: bool,
    target_is_actor: bool,
) -> bool:
    if role == "review_admin":
        return True
    if operation == "create_case":
        return True
    if operation == "assign_case":
        return status == "unassigned" and target_is_actor
    if operation in ("escalate_case", "decide_case"):
        return assignee_is_actor
    return False


@pytest.mark.parametrize("role", _ROLES)
@pytest.mark.parametrize("status", _STATUSES)
@pytest.mark.parametrize("operation", _OPERATIONS)
@pytest.mark.parametrize("assignee_is_actor", [True, False])
@pytest.mark.parametrize("target_is_actor", [True, False])
def test_authorize_operation_matches_the_documented_authority_table(
    role: ActorRole,
    status: CaseStatus | None,
    operation: MutationOperation,
    assignee_is_actor: bool,
    target_is_actor: bool,
) -> None:
    assignee_id = _ACTOR if assignee_is_actor else _OTHER_ACTOR
    target_actor_id = _ACTOR if target_is_actor else _OTHER_ACTOR

    result = authorize_operation(
        operation=operation,
        current_status=status,
        actor_role=role,
        actor_id=_ACTOR,
        assignee_id=assignee_id,
        target_actor_id=target_actor_id,
    )

    assert result == _expected(
        role, operation, status, assignee_is_actor, target_is_actor
    )


def test_self_claim_omits_a_target_actor_id() -> None:
    assert authorize_operation(
        operation="assign_case",
        current_status="unassigned",
        actor_role="reviewer",
        actor_id=_ACTOR,
        assignee_id=None,
        target_actor_id=None,
    )


def test_reviewer_cannot_assign_someone_else_to_an_unassigned_case() -> None:
    assert not authorize_operation(
        operation="assign_case",
        current_status="unassigned",
        actor_role="reviewer",
        actor_id=_ACTOR,
        assignee_id=None,
        target_actor_id=_OTHER_ACTOR,
    )


def test_reviewer_cannot_reassign_or_assign_from_escalated() -> None:
    for status in ("assigned", "escalated"):
        assert not authorize_operation(
            operation="assign_case",
            current_status=status,
            actor_role="reviewer",
            actor_id=_ACTOR,
            assignee_id=_ACTOR,
            target_actor_id=_ACTOR,
        )


def test_reviewer_without_assignee_cannot_escalate_or_decide() -> None:
    for operation in ("escalate_case", "decide_case"):
        assert not authorize_operation(
            operation=operation,
            current_status="assigned",
            actor_role="reviewer",
            actor_id=_ACTOR,
            assignee_id=None,
            target_actor_id=None,
        )
