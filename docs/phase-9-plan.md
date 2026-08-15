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

## Planned package and test map

The approved implementation should extend the existing `veridoc.review`
package rather than create a generic workflow layer:

```text
src/veridoc/review/
├── api.py
├── auth.py
├── config.py
├── models.py
├── page.py
├── protocol.py
├── service.py
├── transitions.py
└── persistence/
    ├── cli.py
    ├── maintenance.py
    ├── migrations.py
    ├── schema.py
    └── sqlite.py
```

Tests should follow the same focused boundaries. Migration, repository,
maintenance, and API tests must use temporary review databases and synthetic
processing results. Browser tests must use synthetic actors and must not require
network access, provider credentials, Tesseract, or a real browser service.

## Exact atomic commit plan

The following is the minimum planned sequence. Each numbered item is one commit
unless the accepted ADRs require the plan to be revised. A behavior and its
smallest inseparable regression test share one commit. No completed item waits
for a later batch commit.

### Decisions and domain contracts

1. `docs: decide Phase 9 actor and session boundary` — add ADR 0008 and its
   decision-index entry.
2. `docs: decide Phase 9 review record boundary` — add ADR 0009 and its index
   entry.
3. `docs: decide Phase 9 retention and recovery boundary` — add ADR 0010 and
   its index entry.
4. `feat: add review identifiers and status models` — add bounded actor, case,
   status, role, and decision types with focused model tests.
5. `feat: add immutable review snapshot model` — add schema-versioned canonical
   `ProcessingResult` serialization, digest generation, and rejection tests.
6. `feat: add review event models` — add bounded event types and event metadata
   with strict validation tests.
7. `feat: add review mutation models` — add assignment, escalation, decision,
   expected-version, reason, and idempotency request models.
8. `feat: add review transition policy` — implement allowed state transitions
   and cover every allowed and forbidden edge.
9. `feat: add review authorization policy` — implement role/assignee decisions
   as pure code with a complete permission matrix test.

### Protocol, configuration, and authentication

10. `feat: add review repository read protocol` — define typed case list/detail
    reads and unavailable/not-found errors.
11. `feat: add review repository mutation protocol` — add create, assign,
    escalate, decide, session, conflict, and idempotency contracts.
12. `feat: add review store configuration` — validate a distinct
    `VERIDOC_REVIEW_DATABASE` path and reject reference/review path reuse.
13. `feat: add review actor configuration` — validate the external actor file,
    stable IDs, roles, unique digests, permissions, and safe errors.
14. `feat: add review authenticator` — compare fixed-length credential digests
    in constant time and test malformed, unknown, duplicate, and valid actors.
15. `feat: add review session policy` — generate opaque tokens, hash stored
    values, enforce fixed expiry, and validate revocation behavior.

If an accepted authentication ADR requires a new package, add it in one separate
`chore:` commit with `pyproject.toml` and `uv.lock` immediately before the first
code that imports it. The recommended bearer/session design uses the standard
library and needs no new runtime dependency.

### Dedicated review persistence

16. `feat: add review migration ledger` — create a forward-only dedicated
    ledger with future-version and concurrent-initialization tests.
17. `feat: migrate review cases and snapshots` — add immutable snapshot and
    current-state columns with exact constraints and migration tests.
18. `feat: migrate append-only review events` — add ordered event storage,
    foreign keys, and unique case/version indexes.
19. `feat: migrate review idempotency keys` — add actor/operation/key uniqueness
    and request/result digest fields.
20. `feat: migrate review sessions` — add unique session digests, actor IDs,
    lifecycle timestamps, and expiry indexes.
21. `feat: validate the review database schema` — require exact tables,
    columns, types, keys, indexes, constraints, ledger, and trigger absence.
22. `feat: create review cases atomically` — store the immutable snapshot,
    initial `case_created` event, and creation idempotency result in one
    transaction.
23. `feat: read review case details` — hydrate and revalidate snapshots, digest,
    current state, and ordered events through the protocol.
24. `feat: list review case summaries` — add bounded filters, stable ordering,
    pagination, and one-snapshot count/page reads.
25. `feat: persist review assignments` — guard state/version/authority and append
    assignment or reassignment events in one transaction.
26. `feat: persist review escalations` — guard assignee/version/reason and append
    the escalation event atomically.
27. `feat: persist review decisions` — guard terminal-state rules and append the
    decision event atomically.
28. `feat: persist review sessions` — create, resolve, expire, and revoke only
    hashed session tokens.
29. `feat: validate persisted review rows` — reject malformed snapshots,
    digests, states, event order, timestamps, actors, and idempotency rows.
30. `test: cover review persistence concurrency` — add deterministic create,
    assignment, decision, stale-version, duplicate-key, and event-order races.

### Review maintenance

31. `feat: add validated review database backup` — add non-mutating online
    backup with integrity, schema, ledger, and row-semantics checks.
32. `feat: add atomic review database restore` — add stopped-service,
    sidecar-safe, migrated temporary validation and destination preservation.
33. `feat: add review maintenance command` — expose a dedicated
    `veridoc-review` backup/restore entry point and commit its metadata and lock
    change together.

### Authentication and HTTP API

34. `feat: resolve authenticated review actors` — add bearer/session
    dependencies that reject callers before repository or processing resolution.
35. `feat: create review browser sessions` — add the session endpoint, secure
    cookie attributes, generic errors, and origin-aware tests.
36. `feat: revoke review browser sessions` — add logout, cookie expiry, and
    repeat-logout behavior.
37. `feat: protect review mutations from CSRF` — validate CSRF token and exact
    origin before any storage work.
38. `feat: bound review case creation bodies` — extend the pre-parser body limit
    to the multipart case route, including mounts, chunked bodies, and trailing
    slashes.
39. `feat: create review cases through processing` — run the existing pipeline
    server-side and publish a case only after successful processing and storage.
40. `feat: list review cases` — add authenticated, bounded, filtered summaries.
41. `feat: read review case details` — return the canonical snapshot, current
    state, and ordered events without secrets or internal storage fields.
42. `feat: assign review cases` — add claim/assign/reassign behavior with version
    preconditions and safe conflicts.
43. `feat: escalate review cases` — add the bounded reason endpoint and
    assignee/admin authorization.
44. `feat: decide review cases` — add terminal decisions, bounded reasons,
    assignee/admin authorization, and repeat-request idempotency.
45. `test: cover review API error contracts` — verify generic validation,
    authentication, authorization, conflict, unavailable, and correlation
    responses across the route family.

### Authenticated review UI

46. `feat: add review login and logout UI` — render no secrets, use secure
    session transport, and test expiry and logout behavior.
47. `feat: list assigned review cases in the UI` — render summaries with text
    nodes only and preserve safe empty/error states.
48. `feat: render immutable review case evidence` — display the canonical
    snapshot and event timeline without trusting provider HTML.
49. `feat: add review assignment actions` — submit versioned, CSRF-protected
    claim and reassignment operations.
50. `feat: add review escalation and decision actions` — submit bounded reasons
    and handle stale or terminal cases safely.

### Integration, packaging, and documentation

51. `test: cover review case creation integration` — retain the real processing
    graph and review service with deterministic external fakes and temporary
    reference/review databases.
52. `test: cover review authorization integration` — prove rejected actors never
    resolve processing, reference, or review storage.
53. `test: cover review retry and recovery integration` — verify idempotent
    creation, concurrent mutations, backup, restore, and snapshot independence
    from the current reference database.
54. `test: validate packaged review contracts` — require review modules, the new
    console entry point, and critical review routes in both distributions.
55. `docs: document the Phase 9 API` — add implemented requests, responses,
    limits, errors, auth, concurrency, and idempotency behavior.
56. `docs: document the Phase 9 architecture` — add review boundaries, state
    flow, immutable snapshots, events, and dependency direction.
57. `docs: document Phase 9 data security` — add actor/session secrets, CSRF,
    review data, retention limits, backup, and recovery rules.
58. `docs: document Phase 9 development and testing` — add configuration,
    maintenance, focused tests, fixtures, and verification commands.
59. `docs: update the Phase 9 project guides` — synchronize README, changelog,
    roadmap status, repository tree, and `AGENTS.md` only after all behavior and
    gates are complete.
60. `docs: record Phase 9 completion evidence` — run and record the complete
    release gate from a clean worktree without claiming hosted CI or production
    readiness.

## Checkpoints and stop conditions

The work must pause after each checkpoint if its focused or full gate fails:

1. **Decision checkpoint:** ADRs are accepted and the remaining plan still
   matches them. No runtime files have changed.
2. **Domain checkpoint:** models, transition rules, authorization, and protocols
   pass without FastAPI or SQLite imports in domain modules.
3. **Persistence checkpoint:** migrations, repository operations, concurrency,
   and maintenance pass before any public review route exists.
4. **Security checkpoint:** actor, session, CSRF, origin, auth-before-storage,
   and safe-error tests pass before workflow APIs are exposed.
5. **API checkpoint:** every route and OpenAPI contract passes before UI work.
6. **UI checkpoint:** login, expiry, logout, rendering, CSRF, actions, and browser
   secret-absence tests pass before integration completion.
7. **Release checkpoint:** the full project and distribution gates pass from a
   clean tree before Phase 9 is marked complete.

Forward-only migrations are never rolled back in place. Before an approved
migration touches an existing review database, operators must create a validated
backup. Recovery uses the stopped-service restore command and the documented
backup, not a downgrade migration or Git history rewrite.

## Required verification

Every code commit runs its focused pytest target, Ruff lint, Ruff format check,
and mypy when production types change. Every documentation commit runs
`tests/test_documentation.py`; development-command changes also run the health
test. Each migration, storage, API, integration, dependency, or cross-cutting
checkpoint runs the full suite.

The Phase 9 completion gate is:

```powershell
uv sync --all-groups --locked
uv lock --check
uv run pip-audit
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov=veridoc
uv build --clear
uv run twine check dist/*
uv run python scripts/check_distribution.py
$wheelPath = (Get-ChildItem dist -Filter *.whl | Select-Object -First 1).FullName
uv run --isolated --no-project --no-cache --with $wheelPath `
  python scripts/smoke_distribution.py
$sdistPath = (Get-ChildItem dist -Filter *.tar.gz | Select-Object -First 1).FullName
uv run --isolated --no-project --no-cache --with $sdistPath `
  python scripts/smoke_distribution.py
git diff --check
git status --short
```

Additional Phase 9 evidence must include:

- every allowed and forbidden transition and permission;
- authentication and authorization before processing or storage resolution;
- secure cookie, session expiry, logout, CSRF, and origin behavior;
- no credentials in HTML, browser storage, URLs, responses, or logs;
- immutable snapshot digest and schema validation;
- append-only ordered events and atomic case/event mutations;
- stale-version and idempotency conflict behavior;
- concurrent create, assignment, escalation, and decision results;
- malformed database rows, future schemas, and migration races;
- backup/restore integrity, sidecar, atomicity, and recovery-boundary behavior;
  and
- synthetic-only complete API and UI integration scenarios.

## Documentation updates at completion

Phase 9 implementation must update these documents only with behavior that has
landed and passed its focused checks:

- `README.md` for capabilities, setup, configuration, commands, tree, phase
  status, and limitations;
- `AGENTS.md` for packages, tests, commands, security rules, and the approved
  phase boundary;
- `CHANGELOG.md` for completed review behavior and limitations;
- `docs/api.md` for the implemented review routes and errors;
- `docs/architecture.md` for dependencies, state, snapshots, and events;
- `docs/data-and-security.md` for identity, sessions, CSRF, retention, and review
  data handling;
- `docs/development.md` for actor, HTTPS origin, database, and maintenance setup;
- `docs/testing.md` for new test modules, commands, fixtures, and gates;
- `docs/roadmap.md` for actual Phase 9 completion and the unchanged Phase 10
  approval gate;
- `docs/decisions/README.md` plus ADRs 0008 through 0010; and
- `docs/release-evidence.md` for the observed local completion gate.

## Approval wording

Implementation must not start from an ambiguous request to “continue” or
“improve the project.” Explicit approval should identify this plan, for example:

> Approve Phase 9 implementation according to `docs/phase-9-plan.md`. Keep
> Phase 10 and Phase 11 unapproved.
