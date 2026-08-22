# 0009: Use immutable versioned review records in a dedicated store

## Status

Accepted

## Context

Phase 9 needs a durable, auditable record of human review decisions around a
`ProcessingResult`. That result must remain trustworthy evidence: it must not
be replaced, edited, or client-supplied, and every state change must be
attributable, ordered, and safe under concurrent requests. The existing
`VERIDOC_REFERENCE_DATABASE` stores approved vendor/PO facts used as
verification input; mixing review workflow data into that database would let
review activity influence, or be confused with, verification reference data.

## Decision

Use a dedicated SQLite database configured by `VERIDOC_REVIEW_DATABASE`, with
its own repository protocol, forward-only migration ledger, schema validator,
row-semantics validator, backup/restore implementation, and maintenance entry
point. It must not share tables, migrations, or maintenance operations with
`VERIDOC_REFERENCE_DATABASE`. The review repository lives under
`veridoc.review` and is not imported by extraction, verification, explanation,
or processing domain logic; FastAPI and SQLite adapters may depend inward on
review models and protocols, but review models and transition rules must not
import those adapters.

Case creation accepts a bounded document plus an `Idempotency-Key`, runs the
existing processing pipeline server-side, and persists the resulting
`ProcessingResult` as a canonical JSON snapshot together with a stable case
ID, snapshot schema version, SHA-256 content digest, creation timestamp,
request correlation ID, creator actor ID, and current review status/version.
Clients cannot submit canonical extraction, findings, explanations, or
verdict fields. No supported update may replace the snapshot or any canonical
field; hydration revalidates the JSON against the declared schema version and
recomputes the digest.

Cases move through `unassigned -> assigned -> escalated/decided` using the
transition table in `docs/phase-9-plan.md`. `decided` is terminal. Every
successful creation or transition appends one ordered, append-only event in
the same transaction, recording case version, event type, actor ID,
timestamp, request ID, idempotency key, prior/resulting state, reason, and
bounded decision metadata. Supported interfaces never update or delete
events.

Every mutation after creation includes the caller's expected case version;
the repository updates only when that version and current state match, then
increments the version and appends the event atomically, returning a typed
conflict for stale requests. Idempotency keys are scoped to actor, operation,
and route, storing a request digest and the resulting case version or
response identifier; a retry with the same key and digest returns the
original result, and reuse with a different input returns a typed conflict.

## Alternatives considered

- Store review cases and events in `VERIDOC_REFERENCE_DATABASE`.
- Allow clients to submit or edit canonical extraction/verification fields on
  a case.
- Allow supported updates or deletes of persisted events.
- Use optimistic concurrency without a typed conflict response, or no
  concurrency control at all.
- Build a generic workflow/state-machine engine instead of the fixed Phase 9
  transition table.

## Consequences

Review activity gets a fully attributable, tamper-evident audit trail
independent of verification reference data, with safe behavior under
concurrent actors. The dedicated database adds a second SQLite store with its
own migration and maintenance surface to operate. The fixed transition table
and immutable-snapshot rule mean Phase 9 supports exactly the reviewer
workflow described in `docs/phase-9-plan.md` and not generic case management;
extending it to new states or editable fields requires a new accepted
decision.
