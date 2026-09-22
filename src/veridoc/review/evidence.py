"""Digest-bound auditor evidence bundles for review cases.

A bundle binds one canonical case rendering — identifiers, status, version,
attribution, timestamps, the complete digest-verified snapshot, and the full
ordered event history — under a canonical bundle digest. Verification is
offline and store-independent: given only the bundle bytes, it re-parses the
schema, recomputes the snapshot and bundle digests, and replays the event
chain (contiguity, attribution, timestamps, and transition legality) using
the same pure transition table the repository enforces. Any tampering after
export fails verification. This module never mutates a case, an event, or
any store.
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Self

from pydantic import AwareDatetime, Field, model_validator

from veridoc.review.models import (
    ActorId,
    CaseDetail,
    EventType,
    MutationOperation,
    ReviewModel,
)
from veridoc.review.transitions import InvalidTransitionError, next_transition

EVIDENCE_BUNDLE_SCHEMA_VERSION = 1

_EVENT_OPERATIONS: dict[EventType, MutationOperation] = {
    "case_created": "create_case",
    "case_assigned": "assign_case",
    "case_reassigned": "assign_case",
    "case_escalated": "escalate_case",
    "case_decided": "decide_case",
}


class EvidenceBundleError(RuntimeError):
    """Raised when evidence bundle bytes are not verifiable."""

    code = "invalid_evidence_bundle"
    message = "The evidence bundle is not verifiable."

    def __init__(self) -> None:
        super().__init__(self.message)


class EvidenceBundle(ReviewModel):
    """One digest-bound, offline-verifiable rendering of a review case."""

    bundle_version: int = Field(ge=1)
    exported_at: AwareDatetime
    exported_by: ActorId
    case: CaseDetail
    bundle_digest: str = Field(pattern=r"^[0-9a-f]{64}$")

    @model_validator(mode="after")
    def _verify_version_chain_and_digest(self) -> Self:
        if self.bundle_version != EVIDENCE_BUNDLE_SCHEMA_VERSION:
            raise ValueError("Unsupported evidence bundle version.")
        _verify_event_chain(self.case)
        if self.bundle_digest != compute_bundle_digest(self):
            raise ValueError("Evidence bundle digest mismatch.")
        return self


def build_evidence_bundle(
    detail: CaseDetail,
    *,
    exported_by: str,
    exported_at: datetime | None = None,
) -> EvidenceBundle:
    """Bind one canonical case rendering under a canonical bundle digest."""
    pending = EvidenceBundle.model_construct(
        bundle_version=EVIDENCE_BUNDLE_SCHEMA_VERSION,
        exported_at=exported_at or datetime.now().astimezone(),
        exported_by=exported_by,
        case=detail,
        bundle_digest="0" * 64,
    )
    return EvidenceBundle(
        bundle_version=pending.bundle_version,
        exported_at=pending.exported_at,
        exported_by=pending.exported_by,
        case=pending.case,
        bundle_digest=compute_bundle_digest(pending),
    )


def verify_evidence_bundle(raw: str | bytes) -> EvidenceBundle:
    """Verify bundle bytes offline and return the bound case rendering."""
    try:
        text = raw.decode("utf-8") if isinstance(raw, bytes) else raw
        bundle = EvidenceBundle.model_validate_json(text)
    except ValueError as exc:
        raise EvidenceBundleError from exc
    return bundle


def compute_bundle_digest(bundle: EvidenceBundle) -> str:
    """Return the SHA-256 hex digest of one canonical bundle rendering."""
    canonical = bundle.model_dump_json(exclude={"bundle_digest"})
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _verify_event_chain(detail: CaseDetail) -> None:
    """Replay one case history against the pure transition table."""
    events = detail.events
    if not events:
        raise ValueError("Evidence case has no events.")
    if detail.version != len(events):
        raise ValueError("Evidence case version does not match its event count.")
    first, last = events[0], events[-1]
    if first.event_type != "case_created" or first.case_version != 1:
        raise ValueError("Evidence case does not start with case creation.")
    if detail.status != last.resulting_status:
        raise ValueError("Evidence case status does not match its last event.")
    if detail.created_at != first.occurred_at or detail.updated_at != last.occurred_at:
        raise ValueError("Evidence case timestamps do not match its events.")
    for expected_version, event in enumerate(events, start=1):
        if event.case_id != detail.case_id:
            raise ValueError("Evidence event carries a foreign case identifier.")
        if event.case_version != expected_version:
            raise ValueError("Evidence events are not contiguous.")
        try:
            expected = next_transition(
                event.prior_status, _EVENT_OPERATIONS[event.event_type]
            )
        except (InvalidTransitionError, KeyError) as exc:
            raise ValueError("Evidence event is not a legal transition.") from exc
        if (
            event.event_type != expected.event_type
            or event.resulting_status != expected.resulting_status
        ):
            raise ValueError("Evidence event is not a legal transition.")
