"""SQLite adapter for the dedicated Phase 9 review store."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from pathlib import Path
from typing import cast
from uuid import uuid4

from veridoc.review.models import (
    ActorId,
    CaseDetail,
    CasePage,
    CaseStatus,
    CaseSummary,
    IdempotentRequest,
    RequestId,
    ReviewEvent,
    ReviewSnapshot,
    hydrate_review_snapshot,
)
from veridoc.review.persistence.migrations import (
    UnsupportedReviewSchemaVersionError,
    migrate,
)
from veridoc.review.persistence.schema import (
    InvalidReviewSchemaError,
    validate_current_schema,
)
from veridoc.review.protocol import IdempotencyConflictError, ReviewDataUnavailableError


class InvalidPersistedReviewDataError(RuntimeError):
    """Raised when stored review rows violate the repository's semantic contract."""


class SQLiteReviewRepository:
    """Persist review cases, events, idempotency keys, and sessions in SQLite."""

    def __init__(self, database_path: str | Path) -> None:
        self._database_path = Path(database_path)

    def initialize(self) -> None:
        """Migrate the review database to the latest supported schema."""
        try:
            self._database_path.parent.mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise ReviewDataUnavailableError from exc
        with self._connection() as connection:
            migrate(connection, validate=validate_current_schema)

    def create_case(
        self,
        *,
        snapshot: ReviewSnapshot,
        creator_actor_id: ActorId,
        request_id: RequestId,
        idempotent_request: IdempotentRequest,
    ) -> CaseDetail:
        """Atomically create one case, its snapshot, and its creation event."""
        with self._connection() as connection:
            existing = _find_idempotency_key(connection, idempotent_request)
            if existing is not None:
                stored_digest, case_row_id = existing
                if stored_digest != idempotent_request.request_digest:
                    raise IdempotencyConflictError
                row = connection.execute(
                    "SELECT * FROM review_cases WHERE id = ?", (case_row_id,)
                ).fetchone()
                return _case_detail_from_row(connection, row)

            case_id = uuid4().hex
            timestamp = _timestamp()
            cursor = connection.execute(
                """
                INSERT INTO review_cases (
                    case_id, status, version, creator_actor_id,
                    created_at, updated_at, snapshot_schema_version,
                    snapshot_digest, snapshot_json
                ) VALUES (?, 'unassigned', 1, ?, ?, ?, ?, ?, ?)
                """,
                (
                    case_id,
                    creator_actor_id,
                    timestamp,
                    timestamp,
                    snapshot.schema_version,
                    snapshot.content_digest,
                    snapshot.model_dump_json(),
                ),
            )
            case_row_id = cast(int, cursor.lastrowid)
            connection.execute(
                """
                INSERT INTO review_events (
                    case_row_id, case_version, event_type, actor_id,
                    occurred_at, request_id, resulting_status
                ) VALUES (?, 1, 'case_created', ?, ?, ?, 'unassigned')
                """,
                (case_row_id, creator_actor_id, timestamp, request_id),
            )
            try:
                connection.execute(
                    """
                    INSERT INTO review_idempotency_keys (
                        actor_id, operation, idempotency_key, request_digest,
                        case_row_id, result_case_version, created_at
                    ) VALUES (?, ?, ?, ?, ?, 1, ?)
                    """,
                    (
                        idempotent_request.actor_id,
                        idempotent_request.operation,
                        idempotent_request.idempotency_key,
                        idempotent_request.request_digest,
                        case_row_id,
                        timestamp,
                    ),
                )
            except sqlite3.IntegrityError as exc:
                raise IdempotencyConflictError from exc

            row = connection.execute(
                "SELECT * FROM review_cases WHERE id = ?", (case_row_id,)
            ).fetchone()
            return _case_detail_from_row(connection, row)

    def get_case(self, case_id: str) -> CaseDetail | None:
        """Return one case's full snapshot, current state, and ordered events."""
        with self._read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM review_cases WHERE case_id = ?", (case_id,)
            ).fetchone()
            return _case_detail_from_row(connection, row) if row is not None else None

    def list_cases(
        self,
        *,
        status: CaseStatus | None,
        assignee_id: ActorId | None,
        offset: int,
        limit: int,
    ) -> CasePage:
        """Return one bounded, filtered page of case summaries."""
        conditions: list[str] = []
        parameters: list[object] = []
        if status is not None:
            conditions.append("status = ?")
            parameters.append(status)
        if assignee_id is not None:
            conditions.append("assignee_id = ?")
            parameters.append(assignee_id)
        where_clause = f" WHERE {' AND '.join(conditions)}" if conditions else ""

        with self._read_connection() as connection:
            total = int(
                connection.execute(
                    f"SELECT COUNT(*) FROM review_cases{where_clause}",
                    parameters,
                ).fetchone()[0]
            )
            rows = connection.execute(
                f"""
                SELECT * FROM review_cases{where_clause}
                ORDER BY id
                LIMIT ? OFFSET ?
                """,
                (*parameters, limit, offset),
            ).fetchall()
            return CasePage(
                records=[_case_summary_from_row(row) for row in rows],
                offset=offset,
                limit=limit,
                total=total,
            )

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(self._database_path)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA foreign_keys = ON")
        return connection

    @contextmanager
    def _connection(self) -> Iterator[sqlite3.Connection]:
        """Translate SQLite failures without leaking database details."""
        try:
            with closing(self._connect()) as connection, connection:
                yield connection
        except (
            sqlite3.Error,
            InvalidPersistedReviewDataError,
            InvalidReviewSchemaError,
            UnsupportedReviewSchemaVersionError,
        ) as exc:
            raise ReviewDataUnavailableError from exc

    @contextmanager
    def _read_connection(self) -> Iterator[sqlite3.Connection]:
        """Hold one consistent snapshot across a compound repository read."""
        with self._connection() as connection:
            connection.execute("BEGIN")
            yield connection


def _find_idempotency_key(
    connection: sqlite3.Connection, request: IdempotentRequest
) -> tuple[str, int] | None:
    row = connection.execute(
        """
        SELECT request_digest, case_row_id FROM review_idempotency_keys
        WHERE actor_id = ? AND operation = ? AND idempotency_key = ?
        """,
        (request.actor_id, request.operation, request.idempotency_key),
    ).fetchone()
    if row is None:
        return None
    return str(row["request_digest"]), int(row["case_row_id"])


def _case_summary_from_row(row: sqlite3.Row) -> CaseSummary:
    try:
        return CaseSummary(
            case_id=row["case_id"],
            status=row["status"],
            version=row["version"],
            creator_actor_id=row["creator_actor_id"],
            assignee_id=row["assignee_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
        )
    except ValueError as exc:
        raise InvalidPersistedReviewDataError from exc


def _case_detail_from_row(
    connection: sqlite3.Connection, row: sqlite3.Row
) -> CaseDetail:
    try:
        snapshot = hydrate_review_snapshot(row["snapshot_json"])
        if (
            snapshot.schema_version != row["snapshot_schema_version"]
            or snapshot.content_digest != row["snapshot_digest"]
        ):
            raise InvalidPersistedReviewDataError
        events = [
            _event_from_row(event_row, case_id=row["case_id"])
            for event_row in connection.execute(
                "SELECT * FROM review_events WHERE case_row_id = ? ORDER BY id",
                (row["id"],),
            ).fetchall()
        ]
        return CaseDetail(
            case_id=row["case_id"],
            status=row["status"],
            version=row["version"],
            creator_actor_id=row["creator_actor_id"],
            assignee_id=row["assignee_id"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            snapshot=snapshot,
            events=events,
        )
    except ValueError as exc:
        raise InvalidPersistedReviewDataError from exc


def _event_from_row(row: sqlite3.Row, *, case_id: str) -> ReviewEvent:
    return ReviewEvent(
        case_id=case_id,
        case_version=row["case_version"],
        event_type=row["event_type"],
        actor_id=row["actor_id"],
        occurred_at=row["occurred_at"],
        request_id=row["request_id"],
        idempotency_key=row["idempotency_key"],
        prior_status=row["prior_status"],
        resulting_status=row["resulting_status"],
        reason=row["reason"],
        decision=row["decision"],
        assigned_actor_id=row["assigned_actor_id"],
        metadata=json.loads(row["metadata_json"]),
    )


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
