"""SQLite backup and restore safety tests for the dedicated review store."""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.processing.models import ProcessingResult, ProcessingVerdict
from veridoc.review.models import IdempotentRequest, build_review_snapshot
from veridoc.review.persistence.maintenance import (
    ReviewDataMaintenanceError,
    backup_database,
    restore_database,
)
from veridoc.review.persistence.migrations import LATEST_SCHEMA_VERSION
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


def test_backup_creates_an_integrity_checked_independent_database(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "review.sqlite"
    backup_path = tmp_path / "backups" / "review.backup.sqlite"
    repository = _repository(database_path)
    first_case_id = _create_case(repository, "key-1")

    result = backup_database(database_path, backup_path)
    _create_case(repository, "key-2")
    backup_repository = _repository(backup_path)

    assert result == backup_path.resolve()
    page = backup_repository.list_cases(
        status=None, assignee_id=None, offset=0, limit=200
    )
    assert [record.case_id for record in page.records] == [first_case_id]


def test_backup_rejects_a_missing_source(tmp_path: Path) -> None:
    with pytest.raises(ReviewDataMaintenanceError):
        backup_database(tmp_path / "missing.sqlite", tmp_path / "out.sqlite")


def test_backup_rejects_the_same_source_and_destination(tmp_path: Path) -> None:
    database_path = tmp_path / "review.sqlite"
    _repository(database_path)

    with pytest.raises(ReviewDataMaintenanceError):
        backup_database(database_path, database_path)


def test_backup_rejects_live_destination_sidecars(tmp_path: Path) -> None:
    database_path = tmp_path / "review.sqlite"
    backup_path = tmp_path / "review.backup.sqlite"
    _repository(database_path)
    (tmp_path / "review.backup.sqlite-wal").write_bytes(b"")

    with pytest.raises(ReviewDataMaintenanceError):
        backup_database(database_path, backup_path)


def test_backup_rejects_destination_at_a_source_sidecar_path(tmp_path: Path) -> None:
    database_path = tmp_path / "review.sqlite"
    _repository(database_path)

    with pytest.raises(ReviewDataMaintenanceError):
        backup_database(database_path, tmp_path / "review.sqlite-wal")


def test_backup_rejects_semantic_corruption_without_replacing_destination(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "review.sqlite"
    backup_path = tmp_path / "review.backup.sqlite"
    repository = _repository(database_path)
    _create_case(repository, "key-1")

    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE review_cases SET snapshot_digest = ?", ("0" * 64,))
        connection.commit()

    backup_path.write_bytes(b"existing backup contents")

    with pytest.raises(ReviewDataMaintenanceError):
        backup_database(database_path, backup_path)

    assert backup_path.read_bytes() == b"existing backup contents"


def test_backup_rejects_case_metadata_that_disagrees_with_its_events(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "review.sqlite"
    backup_path = tmp_path / "review.backup.sqlite"
    repository = _repository(database_path)
    _create_case(repository, "key-1")

    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE review_cases SET creator_actor_id = 'reviewer-2'")
        connection.commit()

    backup_path.write_bytes(b"existing backup contents")

    with pytest.raises(ReviewDataMaintenanceError):
        backup_database(database_path, backup_path)

    assert backup_path.read_bytes() == b"existing backup contents"


@pytest.mark.parametrize(
    "corruption_statement",
    [
        "UPDATE review_idempotency_keys SET request_digest = 'invalid'",
        "UPDATE review_idempotency_keys SET result_case_version = 99",
    ],
)
def test_backup_rejects_invalid_idempotency_records(
    tmp_path: Path, corruption_statement: str
) -> None:
    database_path = tmp_path / "review.sqlite"
    backup_path = tmp_path / "review.backup.sqlite"
    repository = _repository(database_path)
    _create_case(repository, "key-1")

    with sqlite3.connect(database_path) as connection:
        connection.execute(corruption_statement)
        connection.commit()

    backup_path.write_bytes(b"existing backup contents")

    with pytest.raises(ReviewDataMaintenanceError):
        backup_database(database_path, backup_path)

    assert backup_path.read_bytes() == b"existing backup contents"


def test_backup_rejects_an_invalid_session_record(tmp_path: Path) -> None:
    database_path = tmp_path / "review.sqlite"
    backup_path = tmp_path / "review.backup.sqlite"
    repository = _repository(database_path)
    repository.create_session(
        session_digest="b" * 64,
        actor_id="reviewer-1",
        expires_at=datetime(2026, 8, 23, 0, 0, tzinfo=UTC),
    )

    with sqlite3.connect(database_path) as connection:
        connection.execute("UPDATE review_sessions SET session_digest = 'invalid'")
        connection.commit()

    backup_path.write_bytes(b"existing backup contents")

    with pytest.raises(ReviewDataMaintenanceError):
        backup_database(database_path, backup_path)

    assert backup_path.read_bytes() == b"existing backup contents"


def test_backup_rejects_foreign_key_corruption(tmp_path: Path) -> None:
    database_path = tmp_path / "review.sqlite"
    backup_path = tmp_path / "review.backup.sqlite"
    repository = _repository(database_path)
    _create_case(repository, "key-1")

    with sqlite3.connect(database_path) as connection:
        connection.execute(
            """
            INSERT INTO review_events (
                case_row_id, case_version, event_type, actor_id, occurred_at,
                request_id, resulting_status
            ) VALUES (999, 1, 'case_created', 'reviewer-1', '2026-08-22T00:00:00Z',
                      'request-orphan', 'unassigned')
            """
        )
        connection.commit()

    with pytest.raises(ReviewDataMaintenanceError):
        backup_database(database_path, backup_path)


def test_restore_atomically_replaces_the_target_database(tmp_path: Path) -> None:
    source_path = tmp_path / "review.sqlite"
    backup_path = tmp_path / "review.backup.sqlite"
    destination_path = tmp_path / "restored.sqlite"
    repository = _repository(source_path)
    backup_case_id = _create_case(repository, "backup-key")
    backup_database(source_path, backup_path)

    target_repository = _repository(destination_path)
    _create_case(target_repository, "replaced-key")

    result = restore_database(backup_path, destination_path)
    restored_repository = _repository(destination_path)

    assert result == destination_path.resolve()
    page = restored_repository.list_cases(
        status=None, assignee_id=None, offset=0, limit=200
    )
    assert [record.case_id for record in page.records] == [backup_case_id]
    with sqlite3.connect(destination_path) as connection:
        latest = connection.execute(
            "SELECT MAX(version) FROM schema_migrations"
        ).fetchone()[0]
    assert latest == LATEST_SCHEMA_VERSION


def test_restore_rejects_a_missing_backup_source(tmp_path: Path) -> None:
    with pytest.raises(ReviewDataMaintenanceError):
        restore_database(tmp_path / "missing.sqlite", tmp_path / "review.sqlite")


def test_restore_rejects_the_same_source_and_destination(tmp_path: Path) -> None:
    database_path = tmp_path / "review.sqlite"
    _repository(database_path)

    with pytest.raises(ReviewDataMaintenanceError):
        restore_database(database_path, database_path)


def test_restore_rejects_live_source_sidecars(tmp_path: Path) -> None:
    backup_path = tmp_path / "review.backup.sqlite"
    _repository(backup_path)
    (tmp_path / "review.backup.sqlite-wal").write_bytes(b"")

    with pytest.raises(ReviewDataMaintenanceError):
        restore_database(backup_path, tmp_path / "review.sqlite")


def test_restore_rejects_live_destination_sidecars(tmp_path: Path) -> None:
    backup_path = tmp_path / "review.backup.sqlite"
    destination_path = tmp_path / "review.sqlite"
    _repository(backup_path)
    (tmp_path / "review.sqlite-shm").write_bytes(b"")

    with pytest.raises(ReviewDataMaintenanceError):
        restore_database(backup_path, destination_path)


def test_restore_preserves_the_destination_on_a_corrupt_backup(tmp_path: Path) -> None:
    backup_path = tmp_path / "review.backup.sqlite"
    destination_path = tmp_path / "review.sqlite"
    backup_path.write_bytes(b"not a sqlite database")
    _repository(destination_path)

    with pytest.raises(ReviewDataMaintenanceError):
        restore_database(backup_path, destination_path)

    restored_repository = _repository(destination_path)
    page = restored_repository.list_cases(
        status=None, assignee_id=None, offset=0, limit=200
    )
    assert page.total == 0
