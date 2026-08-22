"""Read boundary for the Phase 9 dedicated review store."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from veridoc.review.models import ActorId, CaseDetail, CasePage, CaseStatus


class ReviewDataUnavailableError(RuntimeError):
    """Raised when review data cannot be read or written safely."""

    code = "review_data_unavailable"
    message = "Review data is not available on this server."

    def __init__(self) -> None:
        super().__init__(self.message)


@runtime_checkable
class ReviewCaseReader(Protocol):
    """Read bounded case summaries and one case's full detail."""

    def list_cases(
        self,
        *,
        status: CaseStatus | None,
        assignee_id: ActorId | None,
        offset: int,
        limit: int,
    ) -> CasePage:
        """Return one bounded, filtered page of case summaries."""

    def get_case(self, case_id: str) -> CaseDetail | None:
        """Return one case's full snapshot, current state, and ordered events."""
