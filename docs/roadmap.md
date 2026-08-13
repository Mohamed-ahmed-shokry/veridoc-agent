# Project Roadmap

Veridoc Version 1 invoice and purchase-order reconciliation is complete through
Phase 6. Phase 7 release-engineering hardening and Phase 8 controlled local
reference-data administration are also complete. Later phases are planning
boundaries only and require separate approval before implementation.

## Phase status

| Phase | Scope | Status |
| --- | --- | --- |
| 0-6 | Version 1 application, processing workflow, integration, and documentation | Complete |
| 7 | Release engineering and reproducible quality gates | Complete |
| 8 | Controlled reference-data administration | Complete |
| 9 | Persistent review and audit workflow | Planned; not approved |
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

## Phase 9: persistent review and audit workflow

Status: planned; not approved or implemented.

Goal: add an accountable human-review workflow while preserving the current
processing result as immutable evidence. A `clear` processing verdict remains
distinct from human approval, and no reviewer action may rewrite extraction,
canonical findings, explanations, or the deterministic verdict.

Entry criteria:

- explicit user approval for Phase 9 after a fresh Phase 0-8 release gate;
- an approved actor/authentication ADR covering identity, session or token
  lifecycle, roles, and authorization checks;
- an approved review-record ADR covering immutable snapshots, status
  transitions, reason requirements, optimistic concurrency, and idempotency;
- an approved retention ADR covering review records, audit events, deletion,
  legal holds, and backup interaction; and
- synthetic data only until the later deployment and privacy controls are
  approved.

Planned deliverables:

- strict review-case, assignment, decision, and append-only audit-event models;
- a persistence-neutral `ReviewRepository` protocol and a forward-only SQLite
  implementation isolated from reference-data repository interfaces;
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
  without changing canonical processing facts; and
- backup/restore, migration, retention, and operational documentation for the
  new review store.

Proposed implementation sequence after approval, with one independently
verified concern per commit:

1. Record the actor/authentication, review-record, and retention decisions as
   separate ADR commits.
2. Add strict review identifiers, snapshots, states, decisions, and event models.
3. Add and test the pure review transition policy.
4. Add the `ReviewRepository` protocol and typed conflict/unavailable errors.
5. Add one migration for review cases and immutable processing snapshots.
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
12. Extend the review UI for authenticated case work without embedding secrets
    or trusting provider prose.
13. Extend maintenance validation and backup/restore for review data.
14. Synchronize API, architecture, security, development, testing, changelog,
    README, and operating guidance.
15. Run and record the complete Phase 9 release gate from a clean worktree.

Required verification:

- model and state-machine tests for every allowed and forbidden transition;
- authorization tests proving rejected actors cannot resolve storage or learn
  case contents;
- transaction and race tests for duplicate creation, concurrent assignment,
  repeated decisions, stale versions, and event ordering;
- boundary tests proving retries return the original case while client-supplied
  canonical processing fields are rejected before persistence;
- persistence tests proving stored processing snapshots and prior audit events
  cannot be updated through supported interfaces;
- malformed-row, migration, backup, restore, and retention-policy tests using
  temporary databases; and
- ASGI integration tests using synthetic documents and identities only, plus
  the existing full quality, coverage, audit, and distribution gates.

Exit criteria:

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

- explicit user approval for Phase 10 and either completion of Phase 9 or an
  approved scope exception explaining why deployment precedes it;
- an approved deployment-target and trust-boundary ADR identifying the runtime,
  network edges, managed services, operator responsibilities, and regions;
- a threat model and data classification covering documents, OCR, provider
  requests, reference data, review records, logs, metrics, traces, and backups;
- approved identity, TLS, secret-management, encryption, retention, malware
  handling, and recovery policies; and
- named owners for vulnerability response, credential rotation, backup drills,
  and incident handling.

Planned deliverables:

- a reproducible runtime artifact with a pinned minimal base, non-root user,
  explicit Tesseract language data, read-only application filesystem where
  practical, and declared CPU/memory/temporary-storage limits;
- separate liveness, readiness, and startup behavior that checks only the
  dependencies appropriate to each signal and supports graceful shutdown;
- TLS termination, authenticated processing/review access, authorization at
  every protected boundary, bounded request concurrency, and rate limits;
- external secret injection with rotation and revocation procedures and no
  credentials in images, manifests, logs, or diagnostic responses;
- malware scanning and quarantine before document decoding, with typed failure
  behavior and an operator-controlled release/disposal workflow;
- encrypted database and backup storage, least-privilege access, automated
  retention, scheduled backups, verified restore drills, and recovery targets;
- structured metrics, traces, and logs restricted to approved metadata, with
  redaction tests and documented provider/data residency controls; and
- deployment, rollback, incident, key-rotation, backup, restore, and disposal
  runbooks tied to the chosen environment.

Proposed implementation sequence after approval:

1. Record the deployment/trust-boundary decision and threat model separately.
2. Record identity/TLS, secrets, storage/recovery, malware, and observability
   decisions as focused ADR commits.
3. Add reproducible runtime packaging and a local container smoke test.
4. Add explicit Tesseract language assets and startup validation.
5. Add liveness, readiness, startup, and graceful-shutdown behavior in separate
   commits with dependency-specific tests.
6. Add processing/review authentication, then authorization policies, without
   weakening the Phase 8 administration boundary.
7. Add bounded concurrency and rate limiting with deterministic overload tests.
8. Add the scanning/quarantine boundary before upload decoding.
9. Move sensitive persistence to the selected encrypted storage profile and add
   least-privilege credentials.
10. Automate retention and backups, then verify restore and rollback drills.
11. Add privacy-reviewed metrics, traces, and structured log export.
12. Add artifact provenance, dependency/image scanning, and deployment-policy
    validation to CI.
13. Write the environment-specific operations and incident runbooks.
14. Synchronize public limitations, architecture, security, testing, changelog,
    README, and operating guidance.
15. Run and record the complete Phase 10 deployment-security gate.

Required verification:

- deterministic image builds, package/archive gates, software inventory, and
  vulnerability/policy scans for runtime and deployment artifacts;
- tests proving unauthenticated or unauthorized requests fail before document,
  provider, review, or storage work;
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
- a frozen application, model/provider, OCR/language-data, dependency, runtime,
  and deployment-artifact identity;
- legal/privacy approval for a licensed, representative, access-controlled
  evaluation corpus with documented provenance, permitted uses, retention, and
  disposal;
- a preregistered evaluation protocol defining populations, slices, metrics,
  sample-size requirements, uncertainty reporting, and acceptance thresholds
  before results are inspected; and
- named business, security, privacy, operations, and quality owners empowered to
  accept or reject the measured scope.

Planned deliverables:

- a versioned corpus manifest with license/provenance records, content digests,
  language/layout/vendor/quality slices, and leakage checks, stored outside the
  source repository when documents are sensitive;
- a deterministic evaluation runner that records configuration and artifact
  identities and emits machine-readable, reproducible results;
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

Proposed implementation sequence after approval:

1. Record the evaluation protocol, acceptance authority, and corpus-governance
   decisions before importing or observing evaluation labels.
2. Add the corpus manifest schema and license/provenance validator.
3. Add deterministic artifact/configuration identity capture.
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
  deployment, document population, volume, and operator controls measured;
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
  invalidated by unreviewed material changes.

Explicit non-goals: training a model, tuning against the final evaluation set,
claiming fraud detection, generalizing beyond the measured corpus, certifying
legal/accounting compliance, autonomous payment approval, or approving future
provider/model/deployment versions without comparison evidence.

## Approval rule

Phase 8 is complete; no later phase is approved. Before Phase 9 or any later
phase, inspect the current repository, run the full existing gate, present the
exact implementation and atomic commit plan, identify data/security decisions,
and wait for explicit user approval.
