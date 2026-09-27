"""Tests for the dedicated review-store maintenance CLI."""

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
