# 0007: Use forward-only SQLite migrations

## Status

Accepted

## Context

Phase 8 adds identifiers, provenance, timestamps, and retention metadata to the
Phase 3 reference tables. Existing local databases must upgrade without losing
invoice or purchase-order facts. Operators also need reproducible backup and
restore procedures without introducing a remote database or migration
dependency.

## Decision

Track numbered migrations in a `schema_migrations` table. Apply each missing
migration exactly once and in order within a transaction. An existing Phase 3
database without migration metadata is adopted by idempotently applying the
initial schema migration before later migrations. Refuse to open a database
that reports a migration newer than this application understands.

Migrations are forward-only. Before an application upgrade, create a SQLite
online backup. Backup copies a consistent snapshot without migrating or otherwise
modifying the source. It validates database integrity, applies supported
migrations, and checks the complete ledger and required structure on a disposable
copy before atomically publishing the original snapshot. Restore copies a
validated source backup into a temporary sibling database, applies supported
migrations there, repeats the integrity and schema-structure checks, and then
atomically replaces the configured database. The local service must be stopped
for restore.

## Alternatives considered

- Continue relying only on `CREATE TABLE IF NOT EXISTS` statements.
- Use `PRAGMA user_version` without an auditable migration ledger.
- Add Alembic and SQLAlchemy for the local standard-library adapter.
- Mutate or copy the live database file directly during restore.
- Implement down migrations for every schema change.

## Consequences

Existing local databases gain deterministic upgrade history, and failed
migrations or restores leave the prior database intact. The implementation must
test both fresh creation and Phase 3 upgrade paths. Forward-only migrations mean
rollback restores a pre-upgrade backup rather than attempting destructive schema
reversal. This remains a single-process local operational model, not a remote or
high-availability database design.
