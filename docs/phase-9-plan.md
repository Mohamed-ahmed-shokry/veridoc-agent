# Phase 9 Approval and Implementation Plan

Status: proposed; not approved or implemented.

This document turns the Phase 9 roadmap candidate into an approval-ready plan.
It does not approve Phase 9, create a runtime contract, or supersede an accepted
architecture decision. Phase 0 through Phase 8 remain the implemented product.

## Purpose

Phase 9 would add a local, accountable human-review workflow around an immutable
`ProcessingResult`. It would not change extraction, verification, explanation,
or verdict logic. A deterministic `clear` verdict would remain distinct from a
human decision.

The plan is intentionally local and synthetic-data-only. Deployment identity,
remote access, production TLS, encrypted infrastructure, malware scanning, and
real-document operation remain Phase 10 or later work.

## Verified starting point

The planning baseline is commit `813104c`. On 2026-08-16 the existing Phase 0-8
suite passed with 351 tests and 95.96% branch coverage. Before any approved
implementation begins, the same full gate must pass again from a clean worktree
if the baseline commit has changed.

Current behavior remains authoritative:

- `POST /process` returns a typed result without persisting it;
- `GET /review` is a stateless local display page;
- `VERIDOC_REFERENCE_DATABASE` contains approved reference facts only; and
- `VERIDOC_ADMIN_TOKEN` authenticates reference-data administration only.

## Approval boundary

Approval of this plan would authorize Phase 9 design records and implementation
only. It would not approve Phase 10 deployment work, real data, production use,
automatic payment action, SSO, a remote database, or a persistence-stack change.

The first implementation work must be three accepted decision records:

1. actor identity, credentials, roles, sessions, and authorization;
2. review records, immutable snapshots, events, transitions, concurrency,
   idempotency, and review-store topology; and
3. retention, legal holds, purge authority, backup, restore, and recovery.

If an accepted decision differs materially from the recommendations below, the
remaining atomic plan must be revised before code work continues.

## Recommended decisions

### Actor and session boundary

Use stable local actor identifiers and per-actor high-entropy bearer secrets
behind a typed `ReviewAuthenticator` boundary. The initial local adapter should
read an operator-managed actor file outside the repository containing actor IDs,
roles, and fixed-length secret digests. Raw credentials must never be committed,
stored in the review database, logged, or returned.

Use two roles only:

- `reviewer`: read cases, claim an unassigned case, and act on a case assigned
  to that actor; and
- `review_admin`: read all cases, assign or reassign cases, and perform every
  reviewer action.

The Phase 8 administration token must not authenticate review routes. Dependency
ordering must authenticate and authorize before resolving the review repository
or processing service.

For the browser UI, exchange the actor credential for a random server-side
session. Store only its digest, actor ID, creation time, expiry, and revocation
time. Send the opaque session in an `HttpOnly`, `Secure`, `SameSite=Strict`
cookie. Require a separate CSRF token plus exact configured-origin validation on
every state-changing browser request. Session expiry and logout must invalidate
the server record. No credential or session token may enter `localStorage`,
`sessionStorage`, a URL, rendered HTML, logs, or error bodies.

The authenticated review UI should be unavailable unless an HTTPS review origin
is configured. Phase 10 may replace the local authenticator and TLS profile, but
must preserve stable actor attribution.

### Review-store boundary

Use a dedicated SQLite database configured by `VERIDOC_REVIEW_DATABASE`. It must
have its own repository protocol, migration ledger, schema validator,
row-semantics validator, backup/restore implementation, and maintenance entry
point. It must not share tables, migrations, or maintenance operations with
`VERIDOC_REFERENCE_DATABASE`.

The review repository should be organized under `veridoc.review` and must not be
imported by extraction, verification, explanation, or processing domain logic.
FastAPI and SQLite adapters may depend inward on review models and protocols;
review models and transition rules must not import those adapters.

### Immutable processing snapshot

Case creation must accept a bounded document plus an `Idempotency-Key`. The
server runs the existing processing pipeline and stores the resulting
`ProcessingResult`; clients cannot submit canonical extraction, findings,
explanations, or verdict fields.

Persist a canonical JSON snapshot together with:

- a stable case ID;
- snapshot schema version;
- SHA-256 content digest;
- creation timestamp;
- request correlation ID;
- creator actor ID;
- current review status and version; and
- optional retention and legal-hold metadata selected by the retention ADR.

Hydration must revalidate the JSON as the declared schema version and recompute
the digest. No supported update may replace the snapshot or any canonical field.

### State and event model

Use these case states:

- `unassigned` after successful case creation;
- `assigned` while one actor owns review work;
- `escalated` when a reviewer cannot decide; and
- `decided` after an authorized final decision.

Recommended transitions are:

| Current state | Operation | Next state | Required authority |
| --- | --- | --- | --- |
| none | create case | `unassigned` | authenticated actor |
| `unassigned` | claim or assign | `assigned` | reviewer self-claim or review admin |
| `assigned` | reassign | `assigned` | review admin |
| `assigned` | escalate | `escalated` | assignee or review admin |
| `escalated` | assign | `assigned` | review admin |
| `assigned` | decide | `decided` | assignee or review admin |

`decided` is terminal. Decision values should be `accept`, `reject`, or
`needs_correction`; all require nonblank bounded reason text. Escalation and
reassignment also require reasons. An actor may not decide another actor's case
unless holding the `review_admin` role.

Every successful creation or transition appends one ordered event in the same
transaction. Events contain case version, event type, actor ID, timestamp,
request ID, idempotency key, prior and resulting state, reason, and only the
bounded decision metadata applicable to that event. Supported interfaces never
update or delete events.

### Concurrency and idempotency

Every mutation after creation must include the caller's expected case version.
The repository updates only when that version and current state match, then
increments the version and appends the event atomically. Stale requests return a
typed conflict without changing the case.

Idempotency keys are scoped to actor, operation, and route. Store a request
digest and the resulting case version or response identifier. A retry with the
same key and digest returns the original result; reuse with different input
returns a typed conflict. Failed transactions do not reserve a key.

### Planned HTTP surface

The proposed routes are deliberately narrow:

| Method and path | Purpose |
| --- | --- |
| `POST /review/session` | Exchange a configured actor credential for a browser session |
| `DELETE /review/session` | Revoke the current browser session |
| `POST /review/cases` | Process a bounded document and atomically create a case |
| `GET /review/cases` | List authorized case summaries with bounded pagination |
| `GET /review/cases/{case_id}` | Read the immutable snapshot, current state, and ordered events |
| `PUT /review/cases/{case_id}/assignment` | Claim, assign, or reassign with an expected version |
| `POST /review/cases/{case_id}/escalations` | Escalate an assigned case with a reason |
| `POST /review/cases/{case_id}/decisions` | Record a terminal decision with a reason |

`GET /review` remains the HTML entry point. No generic patch endpoint, snapshot
replacement endpoint, event-edit endpoint, or case-decision deletion endpoint
is planned.

### Storage outline

The review-store ADR should validate at least these managed records:

- `review_schema_migrations` for the forward-only ledger;
- `review_cases` for immutable snapshots and current state/version metadata;
- `review_events` for append-only ordered audit events;
- `review_idempotency_keys` for request digests and stable results; and
- `review_sessions` for hashed opaque session credentials and lifecycle data.

Foreign keys, declared column types, uniqueness, indexes, trigger absence, and
persisted-row semantics must be exact. Application-managed writes should be the
only supported mutation path.

### Retention and recovery recommendation

Phase 9 should remain synthetic and local. It should expose no HTTP deletion
route and perform no automatic purge. The retention ADR must define metadata,
legal-hold semantics, operator authority, and the future purge boundary without
claiming automated enforcement.

Review backup should copy and validate the dedicated review database without
modifying the source. Restore must be stopped-service, sidecar-safe, migrated and
validated on a temporary sibling, and atomically published. Because each case
contains its complete immutable processing snapshot, restoring a review backup
must not require reconstructing the historical reference database used during
processing. Documentation must still record that new processing after restore
uses the currently configured reference database.

## Explicit non-goals

- changing OCR, extraction, verification, explanation, or verdict behavior;
- accepting client-supplied canonical processing results;
- writing review data to the reference database;
- generic workflow automation or arbitrary state machines;
- payment execution or accounting-system writes;
- user self-registration, password reset, SSO, or multi-tenancy;
- remote deployment, production TLS termination, or real customer documents;
- automated retention or legally authoritative audit certification; and
- starting Phase 10 or Phase 11 work.

