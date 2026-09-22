"""Auditor evidence bundle tests: offline build, verify, and tamper cases."""

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.processing.models import ProcessingResult, ProcessingVerdict
from veridoc.review.evidence import (
    EVIDENCE_BUNDLE_SCHEMA_VERSION,
    EvidenceBundle,
    EvidenceBundleError,
    build_evidence_bundle,
    compute_bundle_digest,
    verify_evidence_bundle,
)
from veridoc.review.models import (
    CaseAssignmentRequest,
    CaseDetail,
    CaseEscalationRequest,
    IdempotentRequest,
    build_review_snapshot,
)
from veridoc.review.persistence.sqlite import SQLiteReviewRepository

_EXPORTED_AT = datetime(2026, 9, 22, 12, 0, 0, tzinfo=UTC)


def _snapshot():
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


def _created_case(tmp_path: Path) -> CaseDetail:
    return _repository(tmp_path).create_case(
        snapshot=_snapshot(),
        creator_actor_id="reviewer-1",
        request_id="request-1",
        idempotent_request=IdempotentRequest(
            actor_id="reviewer-1",
            operation="create_case",
            idempotency_key="key-1",
            request_digest="a" * 64,
        ),
    )


def _escalated_case(tmp_path: Path) -> CaseDetail:
    repository = _repository(tmp_path)
    created = repository.create_case(
        snapshot=_snapshot(),
        creator_actor_id="reviewer-1",
        request_id="request-1",
        idempotent_request=IdempotentRequest(
            actor_id="reviewer-1",
            operation="create_case",
            idempotency_key="key-1",
            request_digest="a" * 64,
        ),
    )
    repository.assign_case(
        created.case_id,
        request=CaseAssignmentRequest(expected_version=1),
        actor_id="reviewer-1",
        actor_role="reviewer",
        request_id="request-2",
        idempotent_request=None,
    )
    escalated = repository.escalate_case(
        created.case_id,
        request=CaseEscalationRequest(expected_version=2, reason="Needs a lead."),
        actor_id="reviewer-1",
        actor_role="reviewer",
        request_id="request-3",
        idempotent_request=None,
    )
    assert escalated is not None
    return escalated


def _bundle_json(tmp_path: Path) -> dict:
    detail = _escalated_case(tmp_path)
    bundle = build_evidence_bundle(
        detail, exported_by="reviewer-1", exported_at=_EXPORTED_AT
    )
    return json.loads(bundle.model_dump_json())


def test_evidence_bundle_error_carries_a_safe_code() -> None:
    """Bundle failures expose a stable typed code without case content."""
    assert EvidenceBundleError.code == "invalid_evidence_bundle"
    assert EvidenceBundleError().message == "The evidence bundle is not verifiable."


def test_build_and_verify_round_trip(tmp_path: Path) -> None:
    """An exported bundle verifies offline and preserves the case."""
    detail = _escalated_case(tmp_path)
    bundle = build_evidence_bundle(
        detail, exported_by="reviewer-1", exported_at=_EXPORTED_AT
    )

    verified = verify_evidence_bundle(bundle.model_dump_json())

    assert isinstance(verified, EvidenceBundle)
    assert verified.bundle_version == EVIDENCE_BUNDLE_SCHEMA_VERSION
    assert verified.exported_by == "reviewer-1"
    assert verified.case == detail
    assert verified.bundle_digest == compute_bundle_digest(bundle)


def test_verified_bundle_reserializes_canonically(tmp_path: Path) -> None:
    """Verification preserves the canonical bundle rendering byte for byte."""
    detail = _created_case(tmp_path)
    bundle = build_evidence_bundle(
        detail, exported_by="reviewer-1", exported_at=_EXPORTED_AT
    )
    raw = bundle.model_dump_json()

    assert verify_evidence_bundle(raw).model_dump_json() == raw


def test_verify_rejects_non_json_bytes() -> None:
    """Non-JSON bundle bytes fail with the typed error."""
    with pytest.raises(EvidenceBundleError):
        verify_evidence_bundle(b"\x00\x01not-json")


def test_verify_rejects_wrong_schema() -> None:
    """Schema-violating payloads fail with the typed error."""
    with pytest.raises(EvidenceBundleError):
        verify_evidence_bundle(json.dumps({"bundle_version": 1}))


def test_verify_rejects_snapshot_edits(tmp_path: Path) -> None:
    """Editing the embedded result breaks the snapshot digest."""
    payload = _bundle_json(tmp_path)
    payload["case"]["snapshot"]["result"]["verdict"]["status"] = "review_required"

    with pytest.raises(EvidenceBundleError):
        verify_evidence_bundle(json.dumps(payload))


def test_verify_rejects_dropped_events(tmp_path: Path) -> None:
    """Removing the last event breaks version continuity."""
    payload = _bundle_json(tmp_path)
    payload["case"]["events"].pop()
    payload["case"]["version"] = len(payload["case"]["events"])

    with pytest.raises(EvidenceBundleError):
        verify_evidence_bundle(json.dumps(payload))


def test_verify_rejects_reordered_events(tmp_path: Path) -> None:
    """Swapping two events breaks version contiguity."""
    payload = _bundle_json(tmp_path)
    events = payload["case"]["events"]
    events[1], events[2] = events[2], events[1]

    with pytest.raises(EvidenceBundleError):
        verify_evidence_bundle(json.dumps(payload))


def test_verify_rejects_foreign_case_identifiers(tmp_path: Path) -> None:
    """An event carrying another case identifier fails verification."""
    payload = _bundle_json(tmp_path)
    payload["case"]["events"][1]["case_id"] = "other-case"

    with pytest.raises(EvidenceBundleError):
        verify_evidence_bundle(json.dumps(payload))


def test_verify_rejects_illegal_transitions(tmp_path: Path) -> None:
    """An event type that cannot follow its prior status fails verification."""
    payload = _bundle_json(tmp_path)
    payload["case"]["events"][1]["event_type"] = "case_created"
    payload["case"]["events"][1]["prior_status"] = None

    with pytest.raises(EvidenceBundleError):
        verify_evidence_bundle(json.dumps(payload))


def test_verify_rejects_bundle_digest_edits(tmp_path: Path) -> None:
    """Editing the bundle digest breaks the canonical digest."""
    payload = _bundle_json(tmp_path)
    payload["bundle_digest"] = "b" * 64

    with pytest.raises(EvidenceBundleError):
        verify_evidence_bundle(json.dumps(payload))


def test_verify_rejects_export_metadata_edits(tmp_path: Path) -> None:
    """Editing export metadata breaks the canonical digest."""
    payload = _bundle_json(tmp_path)
    payload["exported_by"] = "reviewer-2"

    with pytest.raises(EvidenceBundleError):
        verify_evidence_bundle(json.dumps(payload))
