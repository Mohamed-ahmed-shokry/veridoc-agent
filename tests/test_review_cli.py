"""Tests for the dedicated review-store maintenance CLI."""

from pathlib import Path

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.processing.models import ProcessingResult, ProcessingVerdict
from veridoc.review.models import IdempotentRequest, build_review_snapshot
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
