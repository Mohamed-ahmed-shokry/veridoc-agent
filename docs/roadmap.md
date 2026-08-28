# Project Roadmap

Veridoc Version 1 invoice and purchase-order reconciliation is complete through
Phase 6. Phase 7 release-engineering hardening, Phase 8 controlled local
reference-data administration, and Phase 9's persistent, authenticated review
workflow are also complete. Later phases are planning boundaries only and
require separate approval before implementation.

## Phase status

| Phase | Scope | Status |
| --- | --- | --- |
| 0-6 | Version 1 application, processing workflow, integration, and documentation | Complete |
| 7 | Release engineering and reproducible quality gates | Complete |
| 8 | Controlled reference-data administration | Complete |
| 9 | Persistent, authenticated review and audit workflow | Complete |
| 10 | Deployment and operational security | Planned; not approved |
| 11 | Evaluation, performance, and production-readiness decision | Planned; not approved |

## Phase 7: release engineering

Phase 7 improves confidence in the existing Version 1 behavior without adding
invoice-processing features or changing its public API.

Completed deliverables:

- configure a strict type checker for the production package while pytest
  validates runtime-negative model tests;
- measure branch-aware test coverage and set an evidence-based minimum gate;
- add CI for locked dependency sync, lint, format, types, tests, lock validation,
  package build, and separate installed wheel/source-distribution smoke testing;
- add dependency vulnerability auditing with documented handling for findings;
- validate source and wheel package contents and metadata;
- create a concise changelog for the completed Version 1 phases;
- keep development, testing, README, and agent commands synchronized; and
- run the complete release gate from a clean worktree.

The verified local completion snapshot is recorded in
[release evidence](release-evidence.md).

Expected atomic commit sequence:

1. Add the type-checker dependency and configuration with the updated lockfile.
2. Correct one focused group of type errors per commit until the gate passes.
3. Add coverage tooling and record the measured baseline.
4. Set the minimum coverage gate and document its rationale.
5. Add one CI workflow containing the verified local quality commands.
6. Add dependency-audit tooling and its documented command.
7. Add package-content plus isolated wheel and source-distribution verification.
8. Add the Version 1 changelog.
9. Synchronize project and operating documentation.
10. Run and record the complete Phase 7 completion gate.

Phase 7 explicitly excludes Docker/container choices, cloud deployment,
authentication, database administration endpoints, review persistence, and a
license selection. Each changes operational or legal scope and belongs to a
separately approved phase or decision.

## Phase 8: controlled reference-data administration

Implemented scope:

- authenticated local administration boundary for fictional/approved invoice
  history and purchase orders;
- validated import with dry-run and atomic replacement behavior;
- explicit schema migrations and backup/restore procedures;
- conflict, provenance, and retention metadata; and
- safe list/add/update/delete APIs that never expose document bodies.

[ADR 0006](decisions/0006-use-bearer-token-for-local-administration.md) selects
the local authentication model, and
[ADR 0007](decisions/0007-use-forward-only-sqlite-migrations.md) selects the
migration strategy. Processing uses `InvoiceRepository`; administration uses
the separate `ReferenceDataAdminRepository` boundary implemented by the same
local SQLite adapter.

Selected boundaries:

- administrative HTTP routes use a dedicated bearer token read from the
  process environment and compared in constant time;
- every managed record has a server identifier plus source, external identifier,
  creation/update time, and optional retention date;
- bulk JSON imports are bounded and fully validated before one SQLite
  transaction, with dry-run and explicit reject, skip, or replace conflicts;
- numbered forward-only migrations upgrade existing local databases;
- backup and restore use SQLite's online backup API plus atomic replacement; and
- administrative responses contain structured reference facts and metadata,
  never uploaded document bytes, OCR text, or model prompts.

Implemented atomic sequence:

1. Recorded the authentication and migration decisions.
2. Added migration tracking and provenance columns with upgrade tests.
3. Added bounded administrative models.
4. Added invoice and purchase-order CRUD in separate repository commits.
5. Added atomic import and conflict handling.
6. Added authentication and one endpoint group per focused commit.
7. Added backup and restore tooling plus its console entry point.
8. Synchronized configuration, API, architecture, development, testing,
   security, changelog, README, and operating guidance.
9. Ran and recorded the complete Phase 8 gate and evidence snapshot.

Phase 8 excludes persistent reviewer workflow, user accounts, role management,
remote database services, production deployment, and document storage. Those
remain later-phase decisions.

The numbered sequences for candidate phases are dependency-ordered work
packages, not commit boundaries. After approval and a fresh repository audit,
each package must be expanded into an exact atomic commit plan. Every behavior,
schema change, adapter, test group, operations control, and documentation topic
must follow the repository's smallest independently verified commit protocol.

## Phase 9: persistent, authenticated review and audit workflow

Status: complete.

The approved design, security decisions, and exact atomic commit sequence are
recorded in the
[Phase 9 approval and implementation plan](phase-9-plan.md); every item in
that plan's sequence is implemented. This section is retained as a design
record; see [architecture](architecture.md) and [the API guide](api.md) for
what actually shipped, and [release evidence](release-evidence.md) for the
verified completion gate.

Goal: add an accountable human-review workflow while preserving the current
processing result as immutable evidence. A `clear` processing verdict remains
distinct from human approval, and no reviewer action may rewrite extraction,
canonical findings, explanations, or the deterministic verdict. This goal is
met: every review case stores a digest-verified, immutable `ProcessingResult`
snapshot, and every subsequent change is an appended event, never an edit.

Entry criteria (satisfied):

- explicit user approval for Phase 9 after a fresh Phase 0-8 release gate;
- synthetic data only until the later deployment and privacy controls are
  approved — Phase 9 tests and fixtures use only fictional actor secrets and
  synthetic documents.

Mandatory design gates before schema, API, or UI implementation (satisfied):

- [ADR 0008](decisions/0008-use-local-actor-file-and-http-only-sessions-for-review.md)
  covers actor identity, session lifecycle, roles, and authorization checks;
- [ADR 0009](decisions/0009-use-immutable-versioned-review-records.md) covers
  immutable snapshots, status transitions, reason requirements, optimistic
  concurrency, idempotency, and the review-store topology and recovery
  boundary;
- [ADR 0010](decisions/0010-defer-automated-review-retention-and-purge.md)
  covers review-record retention: metadata reserved but not enforced, no
  automated purge, and no case-deletion route.

Implemented deliverables:

- strict review-case, assignment, decision, and append-only audit-event models;
- a persistence-neutral `ReviewRepository` protocol and a forward-only SQLite
  implementation isolated from reference-data repository interfaces;
- a separately configured review database with its own migration ledger and
  maintenance commands, preserving the rule that the reference database never
  stores processing results; co-location requires an explicit ADR and security-
  boundary update rather than an implicit schema migration;
- immutable storage of the complete processing result plus its schema version,
  creation time, correlation identifier, and content digest;
- a trusted creation boundary that accepts a bounded document and idempotency
  key, runs the approved processing pipeline server-side, and atomically stores
  its result with the initial `case_created` event; clients cannot submit or
  replace canonical extraction, finding, explanation, or verdict fields;
- an explicit state machine for unassigned, assigned, decided, and escalated
  cases, with authorized transitions and required reason text;
- authenticated, bounded APIs for case creation, list/detail views, assignment,
  and decisions, with version preconditions preventing lost updates;
- a review UI that renders canonical evidence safely and submits decisions
  without changing canonical processing facts, using an explicitly selected
  credential transport with expiry and logout; cookie-based sessions require
  `HttpOnly`, `Secure`, and `SameSite` controls plus CSRF and origin validation,
  and no credential may be embedded or stored in browser `localStorage` or
  `sessionStorage`; and
- backup/restore, migration, retention, and operational documentation for the
  new review store.

Implemented delivery sequence: the same dependency order below was followed,
expanded into the 60-item delivery map recorded in the
[Phase 9 plan](phase-9-plan.md). Its completion record identifies one
co-delivered dependency fix and one unrelated launch-file commit; history was
not rewritten. The sequence covers ADRs, then domain models and transition
policy, the review-store protocol and dedicated SQLite implementation
(cases/snapshots, then append-only events, then idempotency keys and
sessions), authentication and authorization dependencies ahead of storage,
one bounded API group at a time (session, then case creation, list, detail,
assignment, escalation, decision), the authenticated console UI, integration
and packaging tests, and finally documentation and completion evidence:

1. Record the actor/authentication, review-record, and retention decisions as
   separate ADR commits.
2. Add strict review identifiers, snapshots, states, decisions, and event models.
3. Add and test the pure review transition policy.
4. Add the `ReviewRepository` protocol and typed conflict/unavailable errors.
5. Add the dedicated review-store configuration and one migration for review
   cases and immutable processing snapshots.
6. Add one migration for append-only events and required indexes.
7. Implement idempotent case creation from server-produced processing results,
   with digest verification and the initial event in one transaction.
8. Implement assignment with optimistic concurrency.
9. Implement decisions and escalation with append-only event creation in the
   same transaction.
10. Add authentication and authorization dependencies before storage
    resolution.
11. Add one bounded API group at a time: create/list/detail, assignment, then
    decisions.
12. Extend the review UI for authenticated case work with the approved session,
    CSRF/origin, expiry, and logout behavior, without embedding secrets or
    trusting provider prose.
13. Extend maintenance validation and backup/restore for review data.
14. Synchronize API, architecture, security, development, testing, changelog,
    README, and operating guidance.
15. Run and record the complete Phase 9 release gate from a clean worktree.

Required verification (delivered):

- model and state-machine tests for every allowed and forbidden transition;
- authorization tests proving rejected actors cannot resolve storage or learn
  case contents;
- ASGI-transport tests covering login/session transport, CSRF and origin
  rejection, expiry, and logout, plus a structural markup test proving the
  console page never uses `innerHTML`; manual in-browser verification (not
  committed test automation) additionally confirmed no credential reaches
  rendered content, `localStorage`, or `sessionStorage`;
- transaction and race tests for duplicate creation, concurrent assignment,
  repeated decisions, stale versions, and event ordering;
- boundary tests proving retries return the original case while client-supplied
  canonical processing fields are rejected before persistence;
- persistence tests proving stored processing snapshots and prior audit events
  cannot be updated through supported interfaces;
- malformed-row, migration, backup, restore, and retention-policy tests using
  temporary databases;
- recovery tests proving the documented reference and review backup boundaries
  cannot silently produce a mixed or incomplete restored state; and
- ASGI integration tests using synthetic documents and identities only, plus
  the existing full quality, coverage, audit, and distribution gates.

Exit criteria (met):

- every review decision is attributable to an authenticated actor and linked to
  an immutable processing snapshot;
- case creation and every later state change create durable ordered events in
  their respective transactions;
- concurrency conflicts fail safely without lost updates or duplicate events;
- retention and recovery behavior is documented and verified locally; and
- release evidence states the limits of the chosen local identity and storage
  model without claiming production readiness.

Explicit non-goals: payment execution, accounting-system writes, automatic
approval, mutable canonical findings, generic workflow automation, multi-tenant
deployment, SSO, production TLS, and real customer documents. Deployment-grade
identity and infrastructure remain Phase 10 concerns.

## Phase 10: deployment and operational security

Status: planned; not approved or implemented.

Goal: create one reproducible, security-reviewed deployment profile for the
approved application scope. A container, manifest, or successful health check is
not evidence of production readiness; the selected environment must demonstrate
identity, transport, secret, storage, recovery, and privacy controls.

Entry criteria:

- explicit user approval for Phase 10 after Phase 9 is complete and its release
  gate has passed;
- named owners for vulnerability response, credential rotation, backup drills,
  and incident handling.

Mandatory design gates before deployment implementation:

- an approved deployment-target and trust-boundary ADR identifying the runtime,
  network edges, managed services, operator responsibilities, and regions;
- a threat model and data classification covering documents, OCR, provider
  requests, reference data, review records, logs, metrics, traces, and backups;
- approved identity, TLS, secret-management, encryption, retention, malware
  handling, and recovery policies.

Planned deliverables:

- a reproducible runtime artifact with a pinned minimal base, non-root user,
  explicit Tesseract language data, read-only application filesystem where
  practical, and declared CPU/memory/temporary-storage limits;
- separate liveness, readiness, and startup behavior that checks only the
  dependencies appropriate to each signal and supports graceful shutdown;
- TLS termination, authenticated processing/review access, authorization at
  every protected boundary, stable actor attribution, bounded request
  concurrency, and rate limits;
- migration of the Phase 9 actor/session model to the selected deployment
  identity provider and role policy; the Phase 8 shared administration token is
  replaced or disabled for remote access rather than retained as a parallel
  production credential;
- external secret injection with rotation and revocation procedures and no
  credentials in images, manifests, logs, or diagnostic responses;
- malware scanning and quarantine before document decoding, with typed failure
  behavior and an operator-controlled release/disposal workflow;
- encrypted database and backup storage, least-privilege access, automated
  retention, scheduled backups, verified restore drills, and recovery targets;
- a SQLite-compatible single-writer topology on the selected encrypted storage
  profile for reference and review data; replacing SQLite or adding a remote
  database adapter requires a separate explicit stack-change approval and ADR;
- structured metrics, traces, and logs restricted to approved metadata, with
  redaction tests and documented provider/data residency controls; and
- deployment, rollback, incident, key-rotation, backup, restore, and disposal
  runbooks tied to the chosen environment.

Proposed dependency order after approval:

1. Record the deployment/trust-boundary decision and threat model separately.
2. Record identity/TLS, secrets, storage/recovery, malware, and observability
   decisions as focused ADR commits.
3. Add reproducible runtime packaging and a local container smoke test.
4. Add explicit Tesseract language assets and startup validation.
5. Add liveness, readiness, startup, and graceful-shutdown behavior in separate
   commits with dependency-specific tests.
6. Integrate the Phase 9 actor/session model with deployment identity, add
   processing and administration authorization, then replace or disable the
   shared-token administration boundary while preserving audit attribution.
7. Add bounded concurrency and rate limiting with deterministic overload tests.
8. Place the SQLite stores on the selected encrypted single-writer storage
   profile and add least-privilege credentials without changing persistence
   technology.
9. Add encrypted quarantine storage with retention and disposal controls.
10. Add the scanning/quarantine boundary before upload decoding.
11. Automate retention and backups, then verify restore and rollback drills.
12. Add privacy-reviewed metrics, traces, and structured log export.
13. Add artifact provenance, dependency/image scanning, and deployment-policy
    validation to CI.
14. Write the environment-specific operations and incident runbooks.
15. Synchronize public limitations, architecture, security, testing, changelog,
    README, and operating guidance.
16. Run and record the complete Phase 10 deployment-security gate.

Required verification:

- deterministic image builds, package/archive gates, software inventory, and
  vulnerability/policy scans for runtime and deployment artifacts;
- tests proving unauthenticated or unauthorized requests fail before document,
  provider, review, or storage work;
- identity-migration tests proving actor attribution remains stable and the
  shared administration token cannot authenticate remote deployment routes;
- load and overload tests for byte, pixel, concurrency, rate, timeout, and
  temporary-storage limits;
- safe scanner failure, quarantine, release, retention, and disposal tests with
  synthetic files only;
- secret-leak and telemetry-redaction tests across responses, logs, metrics,
  traces, crash paths, and support artifacts;
- liveness/readiness/startup and graceful-shutdown tests during dependency loss;
- encrypted backup, point-in-time or declared recovery, restore, rollback, key
  rotation, and credential-revocation drills in the selected environment; and
- a hosted deployment smoke that records exact artifact identity and environment
  without sending real invoices or invoking unapproved providers.

Exit criteria:

- the selected deployment is reproducible from reviewed source and immutable
  dependencies;
- all exposed routes have documented authentication, authorization, rate, and
  request-size controls;
- secrets and sensitive data remain absent from artifacts and telemetry;
- recovery objectives are stated and met by an observed restore drill;
- rollback and incident procedures are executable by the named operators; and
- evidence clearly says the deployment is a Phase 11 evaluation candidate, not
  yet a production-ready service.

Explicit non-goals: supporting multiple deployment targets, multi-region high
availability, arbitrary OCR engines, customer onboarding, real-document use,
accuracy certification, or a production go-live decision. Those either require
separate approval or belong to Phase 11 evaluation.

## Phase 11: evaluation and readiness decision

Status: planned; not approved or implemented.

Goal: decide whether one exact Veridoc artifact and Phase 10 deployment profile
is ready for a narrowly defined production use. The decision must be based on a
preregistered protocol and traceable evidence, not a demo, aggregate accuracy
number, or absence of observed failures.

Entry criteria:

- explicit user approval for Phase 11 and a completed Phase 10 security gate;
- named business, security, privacy, operations, and quality owners empowered to
  accept or reject the measured scope.

Mandatory gates before corpus access or evaluation execution:

- a frozen application, OCR/language-data, dependency, runtime, and deployment-
  artifact identity, plus an immutable model/provider identity when available;
  otherwise the preregistered protocol must define the observable provider
  identity, drift triggers, and resulting decision limitation;
- legal/privacy approval for a licensed, representative, access-controlled
  evaluation corpus with documented provenance, permitted uses, retention, and
  disposal;
- a preregistered evaluation protocol defining populations, slices, metrics,
  sample-size requirements, uncertainty reporting, and acceptance thresholds
  before results are inspected.

Planned deliverables:

- a versioned corpus manifest with license/provenance records, content digests,
  language/layout/vendor/quality slices, and leakage checks, stored outside the
  source repository when documents are sensitive;
- a deterministic evaluation runner that records configuration and artifact
  identities and emits machine-readable, reproducible results;
- a provider-identity record capturing the most specific immutable model,
  serving, region, and configuration metadata available, plus declared drift
  and re-evaluation triggers when the provider cannot expose a frozen artifact;
- separate OCR character/word error metrics for Arabic, Latin, mixed-language,
  scan-quality, page-count, and layout slices;
- field-level extraction exact-match, precision/recall, null-handling,
  line-item, amount/date, evidence-page, and OCR-span-grounding metrics;
- rule-level verification true/false-positive and true/false-negative results,
  insufficient-history behavior, and deterministic verdict outcomes;
- explanation guardrail, provider-fallback, evidence fidelity, and factual
  consistency results without treating prose preference as factual accuracy;
- end-to-end latency, throughput, concurrency, CPU, memory, temporary-storage,
  provider-cost, overload, and failure-budget measurements;
- dependency-loss, timeout, malformed-input, restart, backup/restore, rollback,
  credential-rotation, and incident-response exercises; and
- a signed go/no-go report tying every acceptance threshold to evidence,
  exceptions, owners, expiry/review date, and the exact approved scope.

Proposed dependency order after approval:

1. Record the evaluation protocol, acceptance authority, and corpus-governance
   decisions before importing or observing evaluation labels.
2. Add the corpus manifest schema and license/provenance validator.
3. Add deterministic artifact/configuration identity capture, including hosted
   provider limitations and drift triggers.
4. Add OCR metrics and slice aggregation with unit-tested reference examples.
5. Add extraction and evidence-grounding metrics.
6. Add verification-rule and verdict metrics.
7. Add explanation/fallback safety metrics.
8. Add uncertainty intervals, minimum-slice counts, and explicit
   not-enough-evidence outcomes.
9. Add performance/resource/cost measurement under declared concurrency.
10. Add failure-injection and recovery exercise harnesses.
11. Add an evaluation comparison gate for OCR, model/provider, dependency, or
    runtime version changes.
12. Run the frozen protocol once on the untouched evaluation corpus and retain
    raw machine-readable results under approved access controls.
13. Produce the decision report without tuning thresholds to the observed run.
14. Synchronize limitations, operations, security, testing, changelog, README,
    and operating guidance with the measured outcome.
15. Record the complete Phase 11 evidence snapshot and decision expiry.

Required verification:

- golden tests for every metric, aggregation, missing-label, confidence-interval,
  slice, and threshold-decision path;
- manifest checks for duplicate/leaked documents, missing provenance, altered
  content, unauthorized paths, and disallowed retention;
- reproducibility checks proving the same frozen inputs yield the same
  deterministic verification and evaluation outputs;
- provider-identity checks that detect every observable model/configuration
  change and force re-evaluation under the preregistered policy;
- blinded or access-separated evaluation operation where practical, with no
  threshold or implementation tuning on the final corpus;
- per-slice results with uncertainty and explicit suppression when the planned
  sample size is not met;
- repeatable performance and recovery exercises on the exact Phase 10 target;
  and
- an independent review of the evidence-to-decision mapping and every accepted
  exception.

Decision outcomes:

- `go` approves only the exact artifact, provider/model, language data,
  deployment, document population, volume, and operator controls measured, and
  is unavailable when the hosted serving scope cannot be reproduced;
- `conditional_go` requires named mitigations, monitoring, restricted scope,
  owners, deadlines, and an automatic expiry; and
- `no_go` records failed thresholds and returns work to the appropriate earlier
  phase without weakening the preregistered criteria.

Exit criteria:

- all required slices meet their minimum evidence counts or are explicitly out
  of scope;
- every acceptance threshold has traceable machine-readable evidence;
- operational and recovery exercises meet their declared objectives;
- residual risks and exceptions have owners and review/expiry dates;
- the decision report states exactly what was and was not measured; and
- any readiness claim is limited to the frozen evaluated configuration and is
  invalidated by unreviewed material changes; an unidentifiable hosted serving
  artifact must be recorded as a reproducibility limitation and cannot receive
  an unconditional `go`.

Explicit non-goals: training a model, tuning against the final evaluation set,
claiming fraud detection, generalizing beyond the measured corpus, certifying
legal/accounting compliance, autonomous payment approval, or approving future
provider/model/deployment versions without comparison evidence.

## Approval rule

Phase 9 is complete; no later phase is approved. Before Phase 10, Phase 11, or
any later phase, inspect the current repository, run the full existing gate,
present the exact implementation and atomic commit plan, identify
data/security decisions, and wait for explicit user approval. Phase 9's
approval was scoped to the
[Phase 9 approval and implementation plan](phase-9-plan.md) alone and did not
extend to Phase 10 or Phase 11; the same rule applies to any future phase's
approval.
