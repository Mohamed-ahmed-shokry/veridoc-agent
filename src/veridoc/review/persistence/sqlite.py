"""SQLite adapter for the dedicated Phase 9 review store."""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterator
from contextlib import closing, contextmanager
from datetime import UTC, datetime
from itertools import pairwise
from pathlib import Path
from typing import cast
from uuid import uuid4

from veridoc.review.models import (
    ActorId,
    ActorRole,
    CaseAssignmentRequest,
    CaseDecisionRequest,
    CaseDetail,
    CaseEscalationRequest,
    CasePage,
    CaseStatus,
    CaseSummary,
    EventType,
    IdempotentRequest,
    MutationOperation,
    RequestId,
    ReviewEvent,
    ReviewSession,
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
from veridoc.review.protocol import (
    IdempotencyConflictError,
    ReassignmentReasonRequiredError,
    ReviewAuthorizationError,
    ReviewDataUnavailableError,
    StaleVersionConflictError,
)
from veridoc.review.transitions import (
    InvalidTransitionError,
    Transition,
    authorize_operation,
    next_transition,
)


class InvalidPersistedReviewDataError(RuntimeError):
    """Raised when stored review rows violate the repository's semantic contract."""


_EVENT_OPERATIONS: dict[EventType, MutationOperation] = {
    "case_created": "create_case",
    "case_assigned": "assign_case",
    "case_reassigned": "assign_case",
    "case_escalated": "escalate_case",
    "case_decided": "decide_case",
}


def validate_persisted_review_data(connection: sqlite3.Connection) -> None:
    """Validate every managed case, event chain, and idempotency record."""
    original_row_factory = connection.row_factory
    try:
        connection.row_factory = sqlite3.Row
        case_rows = connection.execute(
            "SELECT * FROM review_cases ORDER BY id"
        ).fetchall()
        case_versions: dict[int, int] = {}
        for row in case_rows:
            detail = _case_detail_from_row(connection, row)
            case_versions[_stored_integer(row["id"])] = detail.version
        _validate_idempotency_rows(connection, case_versions=case_versions)
    finally:
        connection.row_factory = original_row_factory


def _validate_idempotency_rows(
    connection: sqlite3.Connection, *, case_versions: dict[int, int]
) -> None:
    for row in connection.execute(
        "SELECT * FROM review_idempotency_keys ORDER BY id"
    ).fetchall():
        try:
            IdempotentRequest(
                actor_id=row["actor_id"],
                operation=row["operation"],
                idempotency_key=row["idempotency_key"],
                request_digest=row["request_digest"],
            )
            case_row_id = _stored_integer(row["case_row_id"])
            result_case_version = _stored_integer(row["result_case_version"])
            _stored_aware_datetime(row["created_at"])
        except (TypeError, ValueError) as exc:
            raise InvalidPersistedReviewDataError from exc

        current_version = case_versions.get(case_row_id)
        if (
            current_version is None
            or result_case_version < 1
            or result_case_version > current_version
        ):
            raise InvalidPersistedReviewDataError


def _stored_integer(value: object) -> int:
    if not isinstance(value, int):
        raise InvalidPersistedReviewDataError
    return value


def _stored_aware_datetime(value: object) -> datetime:
    if not isinstance(value, str):
        raise InvalidPersistedReviewDataError
    normalized = value[:-1] + "+00:00" if value.endswith("Z") else value
    parsed = datetime.fromisoformat(normalized)
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise InvalidPersistedReviewDataError
    return parsed


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
                stored_digest, case_row_id, result_case_version = existing
                if stored_digest != idempotent_request.request_digest:
                    raise IdempotencyConflictError
                row = connection.execute(
                    "SELECT * FROM review_cases WHERE id = ?", (case_row_id,)
                ).fetchone()
                if row is None:
                    raise InvalidPersistedReviewDataError
                return _case_detail_from_row(
                    connection, row, result_case_version=result_case_version
                )

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
                    occurred_at, request_id, idempotency_key, resulting_status
                ) VALUES (?, 1, 'case_created', ?, ?, ?, ?, 'unassigned')
                """,
                (
                    case_row_id,
                    creator_actor_id,
                    timestamp,
                    request_id,
                    idempotent_request.idempotency_key,
                ),
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
                return _resolve_after_idempotency_conflict(
                    connection, idempotent_request, exc
                )

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

    def get_idempotent_case(self, *, request: IdempotentRequest) -> CaseDetail | None:
        """Return a matching prior case before external processing is repeated."""
        with self._read_connection() as connection:
            existing = _find_idempotency_key(connection, request)
            if existing is None:
                return None
            stored_digest, case_row_id, result_case_version = existing
            if stored_digest != request.request_digest:
                raise IdempotencyConflictError
            row = connection.execute(
                "SELECT * FROM review_cases WHERE id = ?", (case_row_id,)
            ).fetchone()
            if row is None:
                raise InvalidPersistedReviewDataError
            return _case_detail_from_row(
                connection, row, result_case_version=result_case_version
            )

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

    def assign_case(
        self,
        case_id: str,
        *,
        request: CaseAssignmentRequest,
        actor_id: ActorId,
        actor_role: ActorRole,
        request_id: RequestId,
        idempotent_request: IdempotentRequest | None,
    ) -> CaseDetail | None:
        """Claim, assign, or reassign one case, appending its event atomically."""
        with self._connection() as connection:
            found, replay = _find_replay(connection, idempotent_request)
            if found:
                return replay

            row = connection.execute(
                "SELECT * FROM review_cases WHERE case_id = ?", (case_id,)
            ).fetchone()
            if row is None:
                return None
            if int(row["version"]) != request.expected_version:
                raise StaleVersionConflictError

            target_actor_id = request.actor_id or actor_id
            if not authorize_operation(
                operation="assign_case",
                current_status=row["status"],
                actor_role=actor_role,
                actor_id=actor_id,
                assignee_id=row["assignee_id"],
                target_actor_id=target_actor_id,
            ):
                raise ReviewAuthorizationError

            try:
                transition = next_transition(row["status"], "assign_case")
            except InvalidTransitionError as exc:
                raise StaleVersionConflictError from exc

            if transition.event_type == "case_reassigned" and not request.reason:
                raise ReassignmentReasonRequiredError

            return _apply_transition(
                connection,
                row=row,
                transition=transition,
                actor_id=actor_id,
                request_id=request_id,
                assigned_actor_id=target_actor_id,
                reason=request.reason,
                idempotent_request=idempotent_request,
            )

    def escalate_case(
        self,
        case_id: str,
        *,
        request: CaseEscalationRequest,
        actor_id: ActorId,
        actor_role: ActorRole,
        request_id: RequestId,
        idempotent_request: IdempotentRequest | None,
    ) -> CaseDetail | None:
        """Escalate one assigned case, appending its event atomically."""
        with self._connection() as connection:
            found, replay = _find_replay(connection, idempotent_request)
            if found:
                return replay

            row = connection.execute(
                "SELECT * FROM review_cases WHERE case_id = ?", (case_id,)
            ).fetchone()
            if row is None:
                return None
            if int(row["version"]) != request.expected_version:
                raise StaleVersionConflictError

            if not authorize_operation(
                operation="escalate_case",
                current_status=row["status"],
                actor_role=actor_role,
                actor_id=actor_id,
                assignee_id=row["assignee_id"],
                target_actor_id=None,
            ):
                raise ReviewAuthorizationError

            try:
                transition = next_transition(row["status"], "escalate_case")
            except InvalidTransitionError as exc:
                raise StaleVersionConflictError from exc

            return _apply_transition(
                connection,
                row=row,
                transition=transition,
                actor_id=actor_id,
                request_id=request_id,
                assigned_actor_id=None,
                reason=request.reason,
                idempotent_request=idempotent_request,
            )

    def decide_case(
        self,
        case_id: str,
        *,
        request: CaseDecisionRequest,
        actor_id: ActorId,
        actor_role: ActorRole,
        request_id: RequestId,
        idempotent_request: IdempotentRequest | None,
    ) -> CaseDetail | None:
        """Record one terminal decision, appending its event atomically."""
        with self._connection() as connection:
            found, replay = _find_replay(connection, idempotent_request)
            if found:
                return replay

            row = connection.execute(
                "SELECT * FROM review_cases WHERE case_id = ?", (case_id,)
            ).fetchone()
            if row is None:
                return None
            if int(row["version"]) != request.expected_version:
                raise StaleVersionConflictError

            if not authorize_operation(
                operation="decide_case",
                current_status=row["status"],
                actor_role=actor_role,
                actor_id=actor_id,
                assignee_id=row["assignee_id"],
                target_actor_id=None,
            ):
                raise ReviewAuthorizationError

            try:
                transition = next_transition(row["status"], "decide_case")
            except InvalidTransitionError as exc:
                raise StaleVersionConflictError from exc

            return _apply_transition(
                connection,
                row=row,
                transition=transition,
                actor_id=actor_id,
                request_id=request_id,
                assigned_actor_id=None,
                reason=request.reason,
                decision=request.decision,
                idempotent_request=idempotent_request,
            )

    def create_session(
        self, *, session_digest: str, actor_id: ActorId, expires_at: datetime
    ) -> ReviewSession:
        """Persist one new session for an authenticated actor."""
        with self._connection() as connection:
            created_at = datetime.now(UTC)
            connection.execute(
                """
                INSERT INTO review_sessions (
                    session_digest, actor_id, created_at, expires_at
                ) VALUES (?, ?, ?, ?)
                """,
                (
                    session_digest,
                    actor_id,
                    _format_datetime(created_at),
                    _format_datetime(expires_at),
                ),
            )
            return ReviewSession(
                session_digest=session_digest,
                actor_id=actor_id,
                created_at=created_at,
                expires_at=expires_at,
            )

    def resolve_session(self, session_digest: str) -> ReviewSession | None:
        """Return one session record by digest, or ``None`` when unknown.

        Callers must separately consult
        :func:`veridoc.review.auth.is_session_active` to decide whether the
        returned session is still usable.
        """
        with self._read_connection() as connection:
            row = connection.execute(
                "SELECT * FROM review_sessions WHERE session_digest = ?",
                (session_digest,),
            ).fetchone()
            return _session_from_row(row) if row is not None else None

    def revoke_session(self, session_digest: str) -> None:
        """Mark one session revoked; revoking an already-revoked session is a
        safe no-op.
        """
        with self._connection() as connection:
            connection.execute(
                """
                UPDATE review_sessions
                SET revoked_at = COALESCE(revoked_at, ?)
                WHERE session_digest = ?
                """,
                (_timestamp(), session_digest),
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
) -> tuple[str, int, int] | None:
    row = connection.execute(
        """
        SELECT request_digest, case_row_id, result_case_version
        FROM review_idempotency_keys
        WHERE actor_id = ? AND operation = ? AND idempotency_key = ?
        """,
        (request.actor_id, request.operation, request.idempotency_key),
    ).fetchone()
    if row is None:
        return None
    try:
        return (
            str(row["request_digest"]),
            int(row["case_row_id"]),
            int(row["result_case_version"]),
        )
    except (TypeError, ValueError) as exc:
        raise InvalidPersistedReviewDataError from exc


def _find_replay(
    connection: sqlite3.Connection, idempotent_request: IdempotentRequest | None
) -> tuple[bool, CaseDetail | None]:
    """Return ``(True, detail)`` for a valid replay, else ``(False, None)``."""
    if idempotent_request is None:
        return False, None
    existing = _find_idempotency_key(connection, idempotent_request)
    if existing is None:
        return False, None
    stored_digest, case_row_id, result_case_version = existing
    if stored_digest != idempotent_request.request_digest:
        raise IdempotencyConflictError
    row = connection.execute(
        "SELECT * FROM review_cases WHERE id = ?", (case_row_id,)
    ).fetchone()
    if row is None:
        raise InvalidPersistedReviewDataError
    return True, _case_detail_from_row(
        connection, row, result_case_version=result_case_version
    )


def _resolve_after_idempotency_conflict(
    connection: sqlite3.Connection,
    idempotent_request: IdempotentRequest,
    original_exc: sqlite3.IntegrityError,
) -> CaseDetail:
    """Recover after losing a concurrent idempotency-key insert race.

    A concurrent writer may commit the same (actor, operation, key) between
    our precondition read and our own insert. Roll back this attempt's
    partial writes first, then treat a matching digest as a successful
    replay of the winner's result; a differing (or now-missing) digest is a
    genuine conflict.
    """
    connection.rollback()
    resolved = _find_idempotency_key(connection, idempotent_request)
    if resolved is None:
        raise IdempotencyConflictError from original_exc
    stored_digest, case_row_id, result_case_version = resolved
    if stored_digest != idempotent_request.request_digest:
        raise IdempotencyConflictError from original_exc
    row = connection.execute(
        "SELECT * FROM review_cases WHERE id = ?", (case_row_id,)
    ).fetchone()
    if row is None:
        raise IdempotencyConflictError from original_exc
    return _case_detail_from_row(
        connection, row, result_case_version=result_case_version
    )


def _apply_transition(
    connection: sqlite3.Connection,
    *,
    row: sqlite3.Row,
    transition: Transition,
    actor_id: ActorId,
    request_id: RequestId,
    assigned_actor_id: str | None,
    reason: str | None = None,
    decision: str | None = None,
    idempotent_request: IdempotentRequest | None,
) -> CaseDetail:
    """Apply one guarded transition: update, append its event, and record
    idempotency, atomically within the caller's open transaction.
    """
    new_version = int(row["version"]) + 1
    timestamp = _timestamp()
    resolved_assignee = (
        assigned_actor_id if assigned_actor_id is not None else row["assignee_id"]
    )

    cursor = connection.execute(
        """
        UPDATE review_cases
        SET status = ?, version = ?, assignee_id = ?, updated_at = ?
        WHERE id = ? AND version = ?
        """,
        (
            transition.resulting_status,
            new_version,
            resolved_assignee,
            timestamp,
            row["id"],
            row["version"],
        ),
    )
    if cursor.rowcount == 0:
        raise StaleVersionConflictError

    connection.execute(
        """
        INSERT INTO review_events (
            case_row_id, case_version, event_type, actor_id, occurred_at,
            request_id, idempotency_key, prior_status, resulting_status, reason,
            decision, assigned_actor_id
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            row["id"],
            new_version,
            transition.event_type,
            actor_id,
            timestamp,
            request_id,
            (
                idempotent_request.idempotency_key
                if idempotent_request is not None
                else None
            ),
            row["status"],
            transition.resulting_status,
            reason,
            decision,
            assigned_actor_id,
        ),
    )
    if idempotent_request is not None:
        try:
            connection.execute(
                """
                INSERT INTO review_idempotency_keys (
                    actor_id, operation, idempotency_key, request_digest,
                    case_row_id, result_case_version, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    idempotent_request.actor_id,
                    idempotent_request.operation,
                    idempotent_request.idempotency_key,
                    idempotent_request.request_digest,
                    row["id"],
                    new_version,
                    timestamp,
                ),
            )
        except sqlite3.IntegrityError as exc:
            return _resolve_after_idempotency_conflict(
                connection, idempotent_request, exc
            )

    updated_row = connection.execute(
        "SELECT * FROM review_cases WHERE id = ?", (row["id"],)
    ).fetchone()
    return _case_detail_from_row(connection, updated_row)


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
    connection: sqlite3.Connection,
    row: sqlite3.Row,
    *,
    result_case_version: int | None = None,
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
        _verify_event_sequence(row, events)
        current_detail = CaseDetail(
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
        if result_case_version is None or result_case_version == current_detail.version:
            return current_detail
        if not 1 <= result_case_version <= current_detail.version:
            raise InvalidPersistedReviewDataError

        replay_events = current_detail.events[:result_case_version]
        replay_event = replay_events[-1]
        assignee_id = next(
            (
                event.assigned_actor_id
                for event in reversed(replay_events)
                if event.event_type in {"case_assigned", "case_reassigned"}
            ),
            None,
        )
        return CaseDetail(
            case_id=current_detail.case_id,
            status=replay_event.resulting_status,
            version=result_case_version,
            creator_actor_id=current_detail.creator_actor_id,
            assignee_id=assignee_id,
            created_at=current_detail.created_at,
            updated_at=replay_event.occurred_at,
            snapshot=current_detail.snapshot,
            events=replay_events,
        )
    except ValueError as exc:
        raise InvalidPersistedReviewDataError from exc


def _verify_event_sequence(row: sqlite3.Row, events: list[ReviewEvent]) -> None:
    """Require a gap-free, chained, current event history for one case row."""
    if not events:
        raise InvalidPersistedReviewDataError
    if events[0].event_type != "case_created" or events[0].case_version != 1:
        raise InvalidPersistedReviewDataError
    for expected_version, event in enumerate(events, start=1):
        if event.case_version != expected_version:
            raise InvalidPersistedReviewDataError
        try:
            expected_transition = next_transition(
                event.prior_status, _EVENT_OPERATIONS[event.event_type]
            )
        except InvalidTransitionError as exc:
            raise InvalidPersistedReviewDataError from exc
        if (
            event.event_type != expected_transition.event_type
            or event.resulting_status != expected_transition.resulting_status
        ):
            raise InvalidPersistedReviewDataError
    for previous, current in pairwise(events):
        if current.prior_status != previous.resulting_status:
            raise InvalidPersistedReviewDataError
    last_event = events[-1]
    expected_assignee = next(
        (
            event.assigned_actor_id
            for event in reversed(events)
            if event.event_type in {"case_assigned", "case_reassigned"}
        ),
        None,
    )
    if (
        last_event.resulting_status != row["status"]
        or last_event.case_version != row["version"]
        or expected_assignee != row["assignee_id"]
    ):
        raise InvalidPersistedReviewDataError


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


def _session_from_row(row: sqlite3.Row) -> ReviewSession:
    try:
        return ReviewSession(
            session_digest=row["session_digest"],
            actor_id=row["actor_id"],
            created_at=row["created_at"],
            expires_at=row["expires_at"],
            revoked_at=row["revoked_at"],
        )
    except ValueError as exc:
        raise InvalidPersistedReviewDataError from exc


def _format_datetime(value: datetime) -> str:
    return value.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _timestamp() -> str:
    return datetime.now(UTC).isoformat().replace("+00:00", "Z")
