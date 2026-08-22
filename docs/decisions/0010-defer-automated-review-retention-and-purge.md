# 0010: Defer automated review retention and purge

## Status

Accepted

## Context

Phase 9 review cases hold an immutable processing snapshot plus an
append-only event history, which is exactly the kind of record that later
retention, legal-hold, or deletion policy will apply to. Veridoc remains a
local, synthetic-data-only product with no authenticated multi-operator
deployment, legal review, or compliance sign-off. Building automated
retention enforcement or an HTTP deletion route now would create a purge
capability without the operational and legal controls needed to use it
safely, and would exceed the approved local phase.

## Decision

Phase 9 records retention metadata without enforcing it. Cases may carry an
optional `retention_until` date and legal-hold metadata, consistent with the
existing `retention_until` field already used for reference-data records
(Phase 8). Phase 9 exposes no HTTP deletion route for cases or events and
performs no automatic purge; retention metadata is informational only, for
future operator policy.

Review backup copies and validates the dedicated `VERIDOC_REVIEW_DATABASE`
without modifying the source, following the same pattern as reference-data
backup (ADR 0007 and the existing `maintenance.py`). Restore is
stopped-service, sidecar-safe (no live WAL/SHM/rollback-journal sidecars),
migrated and validated on a temporary sibling, and atomically published only
after integrity, schema, and row-semantics checks succeed. Because each case
stores its complete immutable processing snapshot, restoring a review backup
does not require reconstructing the historical reference database used during
original processing; documentation must state that processing performed
after a restore uses the currently configured reference database, which may
differ from what was in effect when a restored case was created.

## Alternatives considered

- Implement automatic time-based purge of decided cases in Phase 9.
- Add an HTTP deletion or hard-purge route for review cases in Phase 9.
- Treat `retention_until` as enforced deletion rather than informational
  metadata.
- Require restoring the historical reference database alongside a review
  backup to reproduce original processing context.

## Consequences

Operators get accurate provenance and optional retention metadata without a
purge capability that could be misused or fail open. Phase 9 review data is
kept indefinitely by default unless an operator uses external, off-repository
process controls. A later approved phase must define the actual purge
authority, legal-hold enforcement, and any automated retention behavior
before Veridoc can claim compliance with a real records-retention policy.
