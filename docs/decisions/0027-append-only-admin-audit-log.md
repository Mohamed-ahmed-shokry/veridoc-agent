# 0027: Record administration mutations in an append-only audit log

## Status

Accepted

## Context

Phase 12 made vendor bank accounts and tax IDs deterministic fraud
reconciliation inputs, but the reference-data administration boundary
records no history of its own mutations. Every invoice, purchase-order,
and vendor create, update, delete, and bulk import executes without noting
what changed, when, or under which request — only an `updated_at`
timestamp survives. Under the Phase 10 threat model, credential-guessing
against the administration boundary followed by a remit-to account rewrite
would leave no trace of the change itself.

## Decision

Phase 17 adds an append-only `admin_audit_log` table to the reference-data
store via forward-only migration 6, with one entry per mutated record:

- server timestamp, request correlation ID (`X-Request-ID`), actor label,
  operation (`create`, `update`, `delete`, `import`), record type
  (`invoice`, `purchase_order`, `vendor`), server record identifier, and
  canonical before/after JSON images (`null` for create-after/delete-before
  symmetry);
- entries are written post-commit by the administration routes, which are
  the sole record writers; a crash between mutation and entry loses the
  entry while the durable mutation survives, which operators can
  reconstruct by re-exporting record state — accepted as residual risk
  rather than hidden behavior;
- no update or delete path exists for entries through any interface, and
  backup/restore carry the log with the database that owns it;
- rows validate like all persisted rows (required fields, bounded values,
  well-formed JSON), and malformed rows fail maintenance validation;
- operators read the log through `veridoc-reference audit-log` with
  bounded type/record filters and pagination; no HTTP read route is added.

Attribution limits are explicit: the Phase 8 shared administration token
carries no actor identity, so entries record the `admin` token-holder role
plus the request correlation ID — what changed and when, not which human.
Per-actor attribution would require replacing the shared token and belongs
to a separately approved identity phase.

## Alternatives considered

- Pass an audit context into every repository write method for same-transaction entries.
- Store the log outside the reference database in a separate file.
- Add digest chains or signatures over log entries.
- Add an HTTP audit-log read route next to the CRUD routes.
- Log dry-run imports that write nothing.

## Consequences

Every trust-anchor change becomes attributable to a request and replayable
from before/after images, giving operators a detective control against
admin-credential abuse. The price is one extra write per mutation and an
unbounded log table whose growth operators monitor as ordinary database
size; retention/purge policy for the log is deferred like all retention
work. Same-transaction atomicity between mutation and entry is
deliberately not claimed.
