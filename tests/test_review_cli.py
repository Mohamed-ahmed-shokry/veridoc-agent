"""Tests for the dedicated review-store maintenance CLI."""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.processing.models import ProcessingResult, ProcessingVerdict
from veridoc.review.models import (
    CaseAssignmentRequest,
    IdempotentRequest,
    build_review_snapshot,
)
from veridoc.review.persistence.cli import main
from veridoc.review.persistence.sqlite import SQLiteReviewRepository


def _repository(path: Path) -> SQLiteReviewRepository:
    repository = SQLiteReviewRepository(path)
    repository.initialize()
    return repository


def _create_case(repository: SQLiteReviewRepository, key: str) -> str:
    result = ProcessingResult(
        extraction=InvoiceExtraction(document_type="invoice"),
        verdict=ProcessingVerdict(
            status="clear",
            summary="No deterministic verification findings require review.",
            finding_count=0,
        ),
    )
    return repository.create_case(
        snapshot=build_review_snapshot(result),
        creator_actor_id="reviewer-1",
        request_id=f"request-{key}",
        idempotent_request=IdempotentRequest(
            actor_id="reviewer-1",
            operation="create_case",
            idempotency_key=key,
            request_digest="a" * 64,
        ),
    ).case_id


def test_cli_backs_up_and_restores_with_explicit_confirmation(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "review.sqlite"
    backup_path = tmp_path / "review.backup.sqlite"
    repository = _repository(database_path)
    backup_case_id = _create_case(repository, "backup-key")

    backup_status = main(
        ["--database", str(database_path), "backup", "--output", str(backup_path)]
    )
    _create_case(repository, "extra-key")
    refused_status = main(
        ["--database", str(database_path), "restore", "--input", str(backup_path)]
    )
    restore_status = main(
        [
            "--database",
            str(database_path),
            "restore",
            "--input",
            str(backup_path),
            "--confirm-replace",
        ]
    )

    restored = _repository(database_path)
    output = capsys.readouterr()
    page = restored.list_cases(status=None, assignee_id=None, offset=0, limit=200)

    assert backup_status == 0
    assert refused_status == 2
    assert restore_status == 0
    assert "Restore requires --confirm-replace." in output.err
    assert [record.case_id for record in page.records] == [backup_case_id]


def test_cli_returns_a_generic_error_without_exposing_missing_paths(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    missing_path = tmp_path / "private-missing.sqlite"

    status = main(
        [
            "--database",
            str(missing_path),
            "backup",
            "--output",
            str(tmp_path / "backup.sqlite"),
        ]
    )

    output = capsys.readouterr()
    assert status == 1
    assert "maintenance could not be completed safely" in output.err
    assert str(missing_path) not in output.err


def test_cli_defaults_the_database_path_from_the_environment(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    database_path = tmp_path / "configured-review.sqlite"
    monkeypatch.setenv("VERIDOC_REVIEW_DATABASE", str(database_path))
    _repository(database_path)

    status = main(["backup", "--output", str(tmp_path / "backup.sqlite")])
    assert status == 0


def test_cases_list_outputs_formatted_records(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "review.sqlite"
    repository = _repository(database_path)
    case_1 = _create_case(repository, "c1")
    case_2 = _create_case(repository, "c2")

    # Assign case 2
    repository.assign_case(
        case_2,
        request=CaseAssignmentRequest(expected_version=1),
        actor_id="reviewer-2",
        actor_role="reviewer",
        request_id="req-assign",
        idempotent_request=None,
    )

    # List all cases
    status = main(["--database", str(database_path), "cases", "list"])
    assert status == 0
    output = capsys.readouterr().out
    assert "Total review cases: 2" in output
    assert case_1 in output
    assert case_2 in output
    assert "unassigned" in output
    assert "reviewer-2" in output

    # Filter by status
    status = main(
        ["--database", str(database_path), "cases", "list", "--status", "assigned"]
    )
    assert status == 0
    output = capsys.readouterr().out
    assert "Total review cases: 1" in output
    assert case_2 in output
    assert case_1 not in output

    # Filter by assignee
    status = main(
        [
            "--database",
            str(database_path),
            "cases",
            "list",
            "--assignee-id",
            "reviewer-2",
        ]
    )
    assert status == 0
    output = capsys.readouterr().out
    assert "Total review cases: 1" in output
    assert case_2 in output

    # Pagination
    status = main(
        [
            "--database",
            str(database_path),
            "cases",
            "list",
            "--offset",
            "1",
            "--limit",
            "1",
        ]
    )
    assert status == 0
    output = capsys.readouterr().out
    assert "Total review cases: 2" in output
    assert case_2 in output
    assert case_1 not in output


def test_cases_list_rejects_invalid_offset_or_limit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "review.sqlite"
    _repository(database_path)

    status = main(["--database", str(database_path), "cases", "list", "--offset", "-1"])
    assert status == 2
    assert "cases list requires --offset >= 0" in capsys.readouterr().err

    status = main(["--database", str(database_path), "cases", "list", "--limit", "0"])
    assert status == 2
    assert "cases list requires --offset >= 0" in capsys.readouterr().err

    status = main(["--database", str(database_path), "cases", "list", "--limit", "201"])
    assert status == 2
    assert "cases list requires --offset >= 0" in capsys.readouterr().err


def test_cases_get_inspects_case_details(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "review.sqlite"
    repository = _repository(database_path)
    case_id = _create_case(repository, "detail-key")

    repository.assign_case(
        case_id,
        request=CaseAssignmentRequest(expected_version=1),
        actor_id="reviewer-1",
        actor_role="reviewer",
        request_id="req-assign",
        idempotent_request=None,
    )

    status = main(
        ["--database", str(database_path), "cases", "get", "--case-id", case_id]
    )
    assert status == 0
    output = capsys.readouterr().out
    assert f"Case ID: {case_id}" in output
    assert "Status: assigned" in output
    assert "Version: 2" in output
    assert "Assignee: reviewer-1" in output
    assert "Verdict: clear" in output
    assert "Events (2):" in output
    assert "case_created by reviewer-1" in output
    assert "case_assigned by reviewer-1" in output


def test_cases_get_reports_not_found_for_unknown_case(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "review.sqlite"
    _repository(database_path)

    status = main(
        ["--database", str(database_path), "cases", "get", "--case-id", "unknown-case"]
    )
    assert status == 1
    assert "Review case not found: unknown-case" in capsys.readouterr().err


def test_sessions_list_outputs_formatted_records(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "review.sqlite"
    repository = _repository(database_path)
    now = datetime.now(UTC)
    future = now + timedelta(hours=12)
    past = now - timedelta(hours=1)

    repository.create_session(
        session_digest="1" * 64, actor_id="reviewer-1", expires_at=future
    )
    repository.create_session(
        session_digest="2" * 64, actor_id="reviewer-1", expires_at=past
    )
    repository.create_session(
        session_digest="3" * 64, actor_id="reviewer-2", expires_at=future
    )
    repository.revoke_session("3" * 64)

    # Unfiltered
    status = main(["--database", str(database_path), "sessions", "list"])
    assert status == 0
    output = capsys.readouterr().out
    assert "Total review sessions: 3" in output
    assert "[ACTIVE] 1111111111111111..." in output
    assert "[EXPIRED] 2222222222222222..." in output
    assert "[REVOKED] 3333333333333333..." in output

    # Active only
    status = main(
        ["--database", str(database_path), "sessions", "list", "--active-only"]
    )
    assert status == 0
    output = capsys.readouterr().out
    assert "Total review sessions: 1" in output
    assert "[ACTIVE] 1111111111111111..." in output
    assert "2222222222222222" not in output

    # Filtered by actor
    status = main(
        [
            "--database",
            str(database_path),
            "sessions",
            "list",
            "--actor-id",
            "reviewer-2",
        ]
    )
    assert status == 0
    output = capsys.readouterr().out
    assert "Total review sessions: 1" in output
    assert "3333333333333333" in output


def test_sessions_list_rejects_invalid_offset_or_limit(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "review.sqlite"
    _repository(database_path)

    status = main(
        ["--database", str(database_path), "sessions", "list", "--offset", "-1"]
    )
    assert status == 2
    assert "sessions list requires --offset >= 0" in capsys.readouterr().err

    status = main(
        ["--database", str(database_path), "sessions", "list", "--limit", "0"]
    )
    assert status == 2
    assert "sessions list requires --offset >= 0" in capsys.readouterr().err

    status = main(
        ["--database", str(database_path), "sessions", "list", "--limit", "201"]
    )
    assert status == 2
    assert "sessions list requires --offset >= 0" in capsys.readouterr().err


def test_sessions_revoke_by_digest(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "review.sqlite"
    repository = _repository(database_path)
    digest = "a" * 64
    repository.create_session(
        session_digest=digest,
        actor_id="reviewer-1",
        expires_at=datetime.now(UTC) + timedelta(hours=12),
    )

    status = main(
        ["--database", str(database_path), "sessions", "revoke", "--digest", digest]
    )
    assert status == 0
    assert f"Review session revoked: {digest}" in capsys.readouterr().out

    session = repository.resolve_session(digest)
    assert session is not None
    assert session.revoked_at is not None


def test_sessions_revoke_by_actor_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "review.sqlite"
    repository = _repository(database_path)
    future = datetime.now(UTC) + timedelta(hours=12)

    repository.create_session(
        session_digest="1" * 64, actor_id="reviewer-1", expires_at=future
    )
    repository.create_session(
        session_digest="2" * 64, actor_id="reviewer-1", expires_at=future
    )
    repository.create_session(
        session_digest="3" * 64, actor_id="reviewer-2", expires_at=future
    )

    status = main(
        [
            "--database",
            str(database_path),
            "sessions",
            "revoke",
            "--actor-id",
            "reviewer-1",
        ]
    )
    assert status == 0
    assert (
        "Revoked 2 active session(s) for actor: reviewer-1" in capsys.readouterr().out
    )

    s3 = repository.resolve_session("3" * 64)
    assert s3 is not None
    assert s3.revoked_at is None


def test_sessions_revoke_requires_exactly_one_of_digest_or_actor_id(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "review.sqlite"
    _repository(database_path)

    # Neither
    status = main(["--database", str(database_path), "sessions", "revoke"])
    assert status == 2
    assert "exactly one of --digest or --actor-id" in capsys.readouterr().err

    # Both
    status = main(
        [
            "--database",
            str(database_path),
            "sessions",
            "revoke",
            "--digest",
            "a" * 64,
            "--actor-id",
            "reviewer-1",
        ]
    )
    assert status == 2
    assert "exactly one of --digest or --actor-id" in capsys.readouterr().err


def test_sessions_prune_removes_expired_sessions(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "review.sqlite"
    repository = _repository(database_path)
    now = datetime.now(UTC)

    repository.create_session(
        session_digest="1" * 64,
        actor_id="reviewer-1",
        expires_at=now - timedelta(days=5),
    )
    repository.create_session(
        session_digest="2" * 64,
        actor_id="reviewer-1",
        expires_at=now - timedelta(hours=2),
    )
    repository.create_session(
        session_digest="3" * 64,
        actor_id="reviewer-1",
        expires_at=now + timedelta(hours=10),
    )

    # Prune older than 2 days
    status = main(
        [
            "--database",
            str(database_path),
            "sessions",
            "prune",
            "--older-than-days",
            "2",
        ]
    )
    assert status == 0
    assert "Pruned 1 expired review session(s)." in capsys.readouterr().out

    # Prune remaining expired (older than 0 days)
    status = main(["--database", str(database_path), "sessions", "prune"])
    assert status == 0
    assert "Pruned 1 expired review session(s)." in capsys.readouterr().out

    # Future session remains
    remaining = repository.list_sessions()
    assert remaining.total == 1
    assert remaining.records[0].session_digest == "3" * 64


def test_sessions_prune_rejects_negative_older_than_days(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    database_path = tmp_path / "review.sqlite"
    _repository(database_path)

    status = main(
        [
            "--database",
            str(database_path),
            "sessions",
            "prune",
            "--older-than-days",
            "-1",
        ]
    )
    assert status == 2
    assert "sessions prune requires --older-than-days >= 0" in capsys.readouterr().err
