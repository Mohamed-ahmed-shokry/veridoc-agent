"""Structural validation for the current dedicated review-store schema."""

from __future__ import annotations

import sqlite3

from veridoc.review.persistence.migrations import LATEST_SCHEMA_VERSION

_REQUIRED_SCHEMA_COLUMNS = {
    "schema_migrations": frozenset({"version", "applied_at"}),
    "review_cases": frozenset(
        {
            "id",
            "case_id",
            "status",
            "version",
            "creator_actor_id",
            "assignee_id",
            "created_at",
            "updated_at",
            "snapshot_schema_version",
            "snapshot_digest",
            "snapshot_json",
            "retention_until",
            "legal_hold_reason",
        }
    ),
    "review_events": frozenset(
        {
            "id",
            "case_row_id",
            "case_version",
            "event_type",
            "actor_id",
            "occurred_at",
            "request_id",
            "idempotency_key",
            "prior_status",
            "resulting_status",
            "reason",
            "decision",
            "assigned_actor_id",
            "metadata_json",
        }
    ),
    "review_idempotency_keys": frozenset(
        {
            "id",
            "actor_id",
            "operation",
            "idempotency_key",
            "request_digest",
            "case_row_id",
            "result_case_version",
            "created_at",
        }
    ),
    "review_sessions": frozenset(
        {
            "id",
            "session_digest",
            "actor_id",
            "created_at",
            "expires_at",
            "revoked_at",
        }
    ),
}
_REQUIRED_PRIMARY_KEYS = {
    "schema_migrations": ("version",),
    "review_cases": ("id",),
    "review_events": ("id",),
    "review_idempotency_keys": ("id",),
    "review_sessions": ("id",),
}
_REQUIRED_INTEGER_COLUMNS = {
    "schema_migrations": frozenset({"version"}),
    "review_cases": frozenset({"id", "version", "snapshot_schema_version"}),
    "review_events": frozenset({"id", "case_row_id", "case_version"}),
    "review_idempotency_keys": frozenset({"id", "case_row_id", "result_case_version"}),
    "review_sessions": frozenset({"id"}),
}
_REQUIRED_NOT_NULL_COLUMNS = {
    "schema_migrations": frozenset({"applied_at"}),
    "review_cases": frozenset(
        {
            "case_id",
            "status",
            "version",
            "creator_actor_id",
            "created_at",
            "updated_at",
            "snapshot_schema_version",
            "snapshot_digest",
            "snapshot_json",
        }
    ),
    "review_events": frozenset(
        {
            "case_row_id",
            "case_version",
            "event_type",
            "actor_id",
            "occurred_at",
            "request_id",
            "resulting_status",
            "metadata_json",
        }
    ),
    "review_idempotency_keys": frozenset(
        {"actor_id", "operation", "idempotency_key", "request_digest", "created_at"}
    ),
    "review_sessions": frozenset(
        {"session_digest", "actor_id", "created_at", "expires_at"}
    ),
}
_REQUIRED_FOREIGN_KEYS = {
    "review_events": frozenset({("case_row_id", "review_cases", "id", "CASCADE")}),
    "review_idempotency_keys": frozenset(
        {("case_row_id", "review_cases", "id", "CASCADE")}
    ),
}
_REQUIRED_NAMED_UNIQUE_INDEXES: dict[
    str,
    dict[str, tuple[tuple[str, ...], str | None]],
] = {
    "review_events": {
        "review_events_case_version_index": (
            ("case_row_id", "case_version"),
            None,
        ),
    },
}
_REQUIRED_NAMED_INDEXES: dict[str, dict[str, tuple[str, ...]]] = {
    "review_cases": {
        "review_cases_status_index": ("status",),
        "review_cases_assignee_index": ("assignee_id",),
    },
    "review_events": {
        "review_events_case_order_index": ("case_row_id", "id"),
    },
    "review_sessions": {
        "review_sessions_expires_at_index": ("expires_at",),
        "review_sessions_actor_index": ("actor_id",),
    },
}
_REQUIRED_ANONYMOUS_UNIQUE_COLUMNS = {
    "review_cases": ("case_id",),
    "review_idempotency_keys": ("actor_id", "operation", "idempotency_key"),
    "review_sessions": ("session_digest",),
}


class InvalidReviewSchemaError(RuntimeError):
    """Raised when a database does not match the supported current review schema."""


def validate_current_schema(connection: sqlite3.Connection) -> None:
    """Require the complete ledger and current structural review invariants."""
    versions = [
        int(row[0])
        for row in connection.execute(
            "SELECT version FROM schema_migrations ORDER BY version"
        )
    ]
    if versions != list(range(1, LATEST_SCHEMA_VERSION + 1)):
        raise InvalidReviewSchemaError
    for table_name, required_columns in _REQUIRED_SCHEMA_COLUMNS.items():
        table_type = connection.execute(
            "SELECT type FROM sqlite_schema WHERE name = ?",
            (table_name,),
        ).fetchone()
        column_rows = list(
            connection.execute("SELECT * FROM pragma_table_info(?)", (table_name,))
        )
        actual_columns = {str(row[1]) for row in column_rows}
        actual_column_types = {
            str(row[1]): str(row[2]).strip().upper() for row in column_rows
        }
        primary_key = tuple(
            str(row[1])
            for row in sorted(column_rows, key=lambda row: int(row[5]))
            if int(row[5]) > 0
        )
        not_null_columns = {str(row[1]) for row in column_rows if int(row[3]) == 1}
        if (
            table_type is None
            or str(table_type[0]) != "table"
            or actual_columns != required_columns
            or any(
                actual_column_types[column_name]
                != (
                    "INTEGER"
                    if column_name in _REQUIRED_INTEGER_COLUMNS[table_name]
                    else "TEXT"
                )
                for column_name in required_columns
            )
            or primary_key != _REQUIRED_PRIMARY_KEYS[table_name]
            or not _REQUIRED_NOT_NULL_COLUMNS[table_name].issubset(not_null_columns)
        ):
            raise InvalidReviewSchemaError

    triggered_tables = {
        str(row[0])
        for row in connection.execute(
            "SELECT tbl_name FROM sqlite_schema WHERE type = 'trigger'"
        )
    }
    if triggered_tables.intersection(_REQUIRED_SCHEMA_COLUMNS):
        raise InvalidReviewSchemaError

    for table_name, required_foreign_keys in _REQUIRED_FOREIGN_KEYS.items():
        actual_foreign_keys = {
            (str(row[3]), str(row[2]), str(row[4]), str(row[6]).upper())
            for row in connection.execute(
                "SELECT * FROM pragma_foreign_key_list(?)",
                (table_name,),
            )
        }
        if not required_foreign_keys.issubset(actual_foreign_keys):
            raise InvalidReviewSchemaError

    for table_name, required_indexes in _REQUIRED_NAMED_UNIQUE_INDEXES.items():
        indexes = {
            str(row[1]): (bool(row[2]), bool(row[4]))
            for row in connection.execute(
                "SELECT * FROM pragma_index_list(?)",
                (table_name,),
            )
        }
        for index_name, (index_columns, predicate) in required_indexes.items():
            expected_partial = predicate is not None
            if indexes.get(index_name) != (True, expected_partial):
                raise InvalidReviewSchemaError
            if _index_columns(connection, index_name) != index_columns:
                raise InvalidReviewSchemaError
            sql_row = connection.execute(
                "SELECT sql FROM sqlite_schema WHERE type = 'index' AND name = ?",
                (index_name,),
            ).fetchone()
            normalized_sql = (
                " ".join(str(sql_row[0]).upper().split()) if sql_row else ""
            )
            _, separator, actual_predicate = normalized_sql.partition(" WHERE ")
            if predicate is None and separator:
                raise InvalidReviewSchemaError
            if predicate is not None and (
                not separator or actual_predicate != predicate.removeprefix("WHERE ")
            ):
                raise InvalidReviewSchemaError

    for table_name, columns in _REQUIRED_ANONYMOUS_UNIQUE_COLUMNS.items():
        if not _has_anonymous_unique_index(connection, table_name, columns):
            raise InvalidReviewSchemaError

    for table_name, required_query_indexes in _REQUIRED_NAMED_INDEXES.items():
        query_indexes = {
            str(row[1]): (bool(row[2]), bool(row[4]))
            for row in connection.execute(
                "SELECT * FROM pragma_index_list(?)",
                (table_name,),
            )
        }
        for index_name, query_index_columns in required_query_indexes.items():
            if query_indexes.get(index_name) != (False, False):
                raise InvalidReviewSchemaError
            if _index_columns(connection, index_name) != query_index_columns:
                raise InvalidReviewSchemaError


def _has_anonymous_unique_index(
    connection: sqlite3.Connection, table_name: str, columns: tuple[str, ...]
) -> bool:
    indexes = connection.execute(
        "SELECT * FROM pragma_index_list(?)", (table_name,)
    ).fetchall()
    return any(
        bool(row[2])
        and not bool(row[4])
        and _index_columns(connection, str(row[1])) == columns
        for row in indexes
    )


def _index_columns(connection: sqlite3.Connection, index_name: str) -> tuple[str, ...]:
    return tuple(
        str(row[2])
        for row in connection.execute(
            "SELECT * FROM pragma_index_info(?)",
            (index_name,),
        )
    )
