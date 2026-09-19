# Project Roadmap

Veridoc Version 1 invoice and purchase-order reconciliation is complete through
Phase 6. Phase 7 release-engineering hardening, Phase 8 controlled local
reference-data administration, Phase 9's persistent, authenticated review
workflow, Phase 10 deployment and operational security, and Phase 11 evaluation
and production-readiness decision are also complete. Later phases are planning
boundaries only and require separate approval before implementation.

## Phase status

| Phase | Scope | Status |
| --- | --- | --- |
| 0-6 | Version 1 application, processing workflow, integration, and documentation | Complete |
| 7 | Release engineering and reproducible quality gates | Complete |
| 8 | Controlled reference-data administration | Complete |
| 9 | Persistent, authenticated review and audit workflow | Complete |
| 10 | Deployment and operational security | Complete |
| 11 | Evaluation, performance, and production-readiness decision | Complete |
| 12 | Authoritative vendor registry, entity resolution, and bank reconciliation | Complete |

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
  console page never uses `innerHTML`; no real browser or HTTPS-terminating
  proxy was used, so browser cookie enforcement and storage inspection remain
  outside the recorded local evidence;
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

Status: complete.

The approved design, security decisions, container packaging, and maintenance
automation are implemented per ADRs 0011-0017 and documented in the
[Phase 10 operations runbook](runbook.md); every planned deliverable in this
section is completed. See [architecture](architecture.md), [the API guide](api.md),
and [release evidence](release-evidence.md) for the verified completion gate.

Goal: create one reproducible, security-reviewed deployment profile for the
approved application scope. A container, manifest, or successful health check is
not evidence of production readiness; the selected environment must demonstrate
identity, transport, secret, storage, recovery, and privacy controls. This goal
is met: the container deployment profile, loopback admin restriction, OCR
readiness probe, rate/concurrency limits, pre-decode quarantine scanning,
automated backup/retention CLI, and operational telemetry export are fully
verified.

Entry criteria (satisfied):

- explicit user approval for Phase 10 after Phase 9 is complete and its release
  gate has passed;
- named owners for vulnerability response, credential rotation, backup drills,
  and incident handling in [runbook](runbook.md).

Mandatory design gates before deployment implementation (satisfied):

- [ADR 0011](decisions/0011-use-local-container-for-phase-10-deployment.md)
  covers the container runtime and single-writer SQLite topology on encrypted storage;
- [ADR 0012](decisions/0012-threat-model-and-data-classification.md)
  covers the threat model and data classification;
- [ADR 0013](decisions/0013-local-identity-with-proxy-tls.md)
  covers proxy-terminated TLS, local identity, and loopback administration restriction;
- [ADR 0014](decisions/0014-runtime-secret-injection-and-rotation.md)
  covers non-leaking runtime secret injection via entrypoint script and rotation;
- [ADR 0015](decisions/0015-encrypted-single-writer-storage.md)
  covers encrypted single-writer SQLite storage and backup retention;
- [ADR 0016](decisions/0016-scan-uploads-before-decoding.md)
  covers pre-decode upload scanning and operator quarantine storage;
- [ADR 0017](decisions/0017-operational-only-telemetry.md)
  covers operational-only telemetry registry and `/metrics` JSON export.

Implemented deliverables:

- a reproducible container artifact with a pinned Debian base (`python:3.12.12-slim-bookworm`),
  non-root user `veridoc` (UID 10001), packaged Arabic and English Tesseract language data,
  and mounts for `/data` and `/secrets`;
- separate liveness (`GET /health`) and readiness (`GET /ready`) endpoints; `/ready`
  validates the OCR executable, `TESSDATA_PREFIX` language assets (`eng` and `ara`),
  and current migration schemas for both the reference and review databases;
- reverse proxy TLS termination guidance, loopback-only caller restriction for
  reference-data administration, bounded request concurrency (`ConcurrencyLimiter`),
  and per-client rate limiting (`RateLimiter`);
- external secret injection via `scripts/entrypoint.sh` preventing environment leakage
  in images, manifests, and diagnostic outputs;
- pre-decode malware scanning and quarantine abstraction (`QuarantineStore`, `ClamAVScannerStub`,
  `ScanStatus`), isolating suspicious uploads before PDF or image parsing;
- encrypted database and backup storage conventions, automated retention keeping the 2
  most recent verified backups per store, and quarantine expired record disposal CLI
  (`veridoc-backup`);
- operational-only telemetry registry (`TelemetryRegistry`) and structured, redacted
  JSON metrics export at `GET /metrics`; and
- environment-specific operations and incident runbooks in [runbook](runbook.md).

Required verification (delivered):

- container packaging contract tests (`tests/test_container_packaging.py`) asserting
  pinned base, non-root user, multi-language tesseract runtime, secret mounting, and
  CI container build step in `.github/workflows/ci.yml`;
- loopback enforcement tests proving remote non-loopback clients receive HTTP 503
  before repository resolution or token comparison;
- readiness probe tests (`tests/test_readiness.py`) proving missing OCR binary, missing
  language traineddata files, or outdated database schemas report degraded or fail safely;
- rate limiting and concurrency tests (`tests/test_deployment_limits.py`) verifying
  HTTP 429 and HTTP 503 rejection contracts under load;
- safe upload scanning and quarantine tests (`tests/test_quarantine_storage.py`,
  `tests/test_quarantine_scanner.py`, `tests/test_quarantine_integration.py`) covering
  scan-before-decode, quarantine isolation, operator retrieval, and disposal;
- automated deployment maintenance tests (`tests/test_deployment_maintenance.py`) verifying
  backup creation, retention pruning (2 most recent verified backups), and quarantine
  expired record disposal;
- telemetry tests (`tests/test_telemetry.py`) covering request counters, route classification,
  status codes, limit counters, scan counters, and sensitive field redaction; and
- full quality gate passing (tests, coverage, mypy, ruff, pip-audit, twine, check_distribution).

Exit criteria (met):

- the deployment container profile is fully reproducible from reviewed source and pinned base;
- all exposed routes have documented authentication, authorization, rate, and request-size controls;
- secrets, document bodies, and sensitive data remain absent from container images and telemetry;
- recovery objectives and automated backup retention are verified by tests;
- incident response, secret rotation, and restore procedures are detailed in [runbook](runbook.md); and
- evidence confirms the deployment profile is ready for Phase 11 evaluation.

Explicit non-goals: multi-region clustering, remote distributed databases, arbitrary OCR engines,
customer onboarding, real-document use, or production go-live without Phase 11 evaluation.

## Phase 11: evaluation and readiness decision

Status: complete.

Goal: decide whether one exact Veridoc artifact and Phase 10 deployment profile
is ready for a narrowly defined production use. The decision is based on a
preregistered protocol and traceable evidence, not a demo, aggregate accuracy
number, or absence of observed failures.

The preregistered protocol is documented in [evaluation protocol](evaluation-protocol.md),
and the baseline benchmark decision is recorded in [evaluation report](evaluation-report.md).

Implemented deliverables:

- Architecture Decision Records ([ADR 0018](decisions/0018-preregistered-evaluation-protocol-and-thresholds.md),
  [ADR 0019](decisions/0019-provider-identity-capture-and-drift-triggers.md),
  [ADR 0020](decisions/0020-corpus-governance-and-synthetic-manifest-schema.md))
  establishing preregistered thresholds, observable provider drift triggers,
  and synthetic corpus governance;
- strict evaluation domain models in `veridoc.evaluation.models` (`EvaluationCorpusManifest`,
  `EvaluationRunRecord`, `DecisionReport`, `SliceMetricsSummary`, `WilsonScoreConfidenceInterval`);
- versioned corpus manifest parser and license/provenance validator in `veridoc.evaluation.manifest`
  enforcing SHA-256 integrity, path safety, and prohibited PI/leakage checks;
- slice-level metrics for OCR character and word error rates (CER/WER) in `veridoc.evaluation.metrics.ocr`;
- field-level extraction exact-match, normalized token F1, and evidence grounding metrics in
  `veridoc.evaluation.metrics.extraction`;
- verification rule confusion matrices (TPR/TNR/FPR/FNR) and verdict concordance metrics in
  `veridoc.evaluation.metrics.verification`;
- explanation guardrail violation, fallback necessity, and factual fidelity metrics in
  `veridoc.evaluation.metrics.explanation`;
- runtime artifact and provider identity capture in `veridoc.evaluation.identity` tracking git
  commit, package versions, language data, and model parameters with hard/soft drift classification;
- deterministic evaluation runner in `veridoc.evaluation.runner` computing slice metrics and
  Wilson score confidence intervals (95% confidence) for sample uncertainty;
- threshold-driven decision evaluator in `veridoc.evaluation.decision` mapping observed metrics
  against preregistered gates to yield transparent `go`, `conditional_go`, or `no_go` reports;
- `veridoc-evaluate` CLI entry point with `run`, `benchmark`, and `check-drift` subcommands; and
- synthetic evaluation corpus benchmark in `tests/fixtures/corpus/` enabling offline deterministic
  readiness verification.

Implemented atomic sequence:

1. Recorded the evaluation protocol, drift triggers, and corpus governance decisions (ADR 0018-0020).
2. Added evaluation domain models and schemas.
3. Added corpus manifest schema and license/provenance validator.
4. Added OCR character and word error rate metrics.
5. Added field-level extraction and evidence-grounding metrics.
6. Added verification rule, verdict concordance, and explanation metrics.
7. Added artifact and provider identity capture and drift detection.
8. Added deterministic evaluation runner and uncertainty intervals.
9. Added evaluation decision evaluator and go/no-go report generator.
10. Added `veridoc-evaluate` CLI entry point and synthetic corpus benchmark.
11. Added preregistered evaluation protocol and baseline decision report.
12. Synchronized project documentation, roadmap, and operating guides.
13. Recorded the verified completion snapshot.

Explicit non-goals: training a model, tuning against the final evaluation set,
claiming fraud detection, generalizing beyond the measured corpus, certifying
legal/accounting compliance, autonomous payment approval, or approving future
provider/model/deployment versions without comparison evidence.

## Phase 12: authoritative vendor registry, entity resolution, and bank reconciliation

Status: complete.

Goal: establish authoritative vendor master data, multi-attribute entity
resolution, and deterministic remit-to bank account and tax reconciliation rules
to prevent payment redirection fraud.

Implemented deliverables:

- Architecture Decision Records ([ADR 0021](decisions/0021-vendor-master-registry-and-schema.md),
  [ADR 0022](decisions/0022-multi-attribute-vendor-entity-resolution.md),
  [ADR 0023](decisions/0023-deterministic-vendor-and-bank-reconciliation-rules.md))
  governing vendor master schema, cascading resolution tiers, and deterministic
  bank/tax reconciliation rules;
- strict vendor master domain schemas in `veridoc.vendors.models` (`VendorEntity`,
  `VendorBankAccount`, `VendorTaxId`, `VendorResolutionResult`, `VendorMatchConfidence`);
- SQLite Migration 5 establishing `vendors`, `vendor_aliases`, `vendor_bank_accounts`,
  and `vendor_tax_ids` tables with unique indexes, foreign key constraints, and
  schema validation;
- repository protocol `VendorRepository` and SQLite persistence implementation in
  `veridoc.persistence.sqlite`;
- deterministic cascading multi-attribute entity resolution engine in
  `veridoc.vendors.resolution` matching across tax IDs, bank accounts, canonical keys,
  aliases, and token similarity;
- deterministic verification rules in `veridoc.verification.vendor_rules` for
  `unregistered_vendor`, `suspended_vendor`, `vendor_bank_account_mismatch`, and
  `vendor_tax_id_mismatch`;
- integration into `ProcessingResult`, processing graph, and service attaching
  authoritative vendor resolution outcomes to every processed invoice;
- loopback-isolated, Bearer-authenticated vendor master data administration API
  (`/admin/reference-data/vendors`) and bulk JSON import support;
- `veridoc-reference vendors` CLI subcommands (`list`, `get`, `delete`); and
- authenticated review console integration rendering vendor entity resolution badges
  and bank account verification indicators safely without `innerHTML`.

Explicit non-goals: remote enterprise ERP synchronization, automated ACH/wire
execution, external bank API integration, dynamic fuzzy threshold tuning, or
speculative machine learning classifiers.

## Approval rule

Phases 0 through 12 are complete. Any future phase, major architectural change,
or production deployment target beyond the evaluated scope requires explicit user
approval, a detailed implementation plan, and compliance with the repository's
atomic commit and testing protocol.

