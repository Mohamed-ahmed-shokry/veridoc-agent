# 0003: Use SQLite for Phase 3 reference data

## Status

Accepted

## Context

Phase 3 needs persistent invoice history and purchase-order facts for
deterministic duplicate, reconciliation, and anomaly checks. The repository
must be usable in local tests without a service dependency while keeping domain
verification independent of SQLite connection code. Phase 3 does not add a
public processing API, database URL configuration, migrations, or a production
deployment model.

## Decision

Use SQLite from the Python standard library behind the `InvoiceRepository`
protocol. `SQLiteInvoiceRepository` explicitly initializes local tables for
vendor invoices, purchase orders, and their line items. Amounts are stored as
text and reconstructed as `Decimal`; dates use ISO-8601 text. The verification
service receives only the protocol, never a SQLite connection.

## Alternatives considered

- Keep reference data in process memory.
- Couple deterministic verification directly to `sqlite3` calls.
- Introduce a remote database service before a public processing boundary exists.

## Consequences

Phase 3 gains deterministic local persistence and integration tests using only
fictional data. Local database files remain ignored by Git. The current schema
is deliberately small and has no migration or multi-process operational model;
those concerns require a later approved deployment phase. A future adapter can
implement the same repository protocol without changing verification rules.
