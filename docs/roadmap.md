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
7. Implement case creation and retrieval with digest verification.
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
- persistence tests proving stored processing snapshots and prior audit events
  cannot be updated through supported interfaces;
- malformed-row, migration, backup, restore, and retention-policy tests using
  temporary databases; and
- ASGI integration tests using synthetic documents and identities only, plus
  the existing full quality, coverage, audit, and distribution gates.

Exit criteria:

- every review decision is attributable to an authenticated actor and linked to
  an immutable processing snapshot;
- every state change creates a durable ordered event in the same transaction;
- concurrency conflicts fail safely without lost updates or duplicate events;
- retention and recovery behavior is documented and verified locally; and
- release evidence states the limits of the chosen local identity and storage
  model without claiming production readiness.

Explicit non-goals: payment execution, accounting-system writes, automatic
approval, mutable canonical findings, generic workflow automation, multi-tenant
deployment, SSO, production TLS, and real customer documents. Deployment-grade
identity and infrastructure remain Phase 10 concerns.

## Phase 10: deployment and operational security

Candidate scope:

- deployment target and container/base-image decision;
- Tesseract language-data packaging and health/readiness behavior;
- TLS termination, authentication enforcement, secret management, and rate
  limits;
- malware scanning and document quarantine boundaries;
- database encryption, backup, recovery, and lifecycle controls; and
- structured log/metric/trace export with privacy review.

No production-readiness claim is allowed merely because a container or cloud
manifest exists. The deployment must demonstrate its security and recovery
controls in the selected environment.

## Phase 11: evaluation and readiness decision

Candidate scope:

- licensed representative evaluation corpus and documented provenance;
- extraction, verification, explanation, latency, and resource benchmarks;
- Arabic/Latin OCR evaluation and known-layout coverage;
- failure-budget, concurrency, and recovery exercises;
- model/provider version-change evaluation; and
- an evidence-backed go/no-go production-readiness report.

Evaluation results must separate OCR/extraction quality from deterministic rule
coverage. They must not be generalized beyond the measured corpus or deployment
environment.

## Approval rule

Phase 8 is complete; no later phase is approved. Before Phase 9 or any later
phase, inspect the current repository, run the full existing gate, present the
exact implementation and atomic commit plan, identify data/security decisions,
and wait for explicit user approval.
