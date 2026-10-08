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
| 13 | Evaluation remediation through corpus expansion | Complete |
| 14 | Measured re-verification and readiness decision update | Planned; blocked on a Tesseract-equipped operator environment |
| 15 | Auditor evidence export for review cases | Complete |
| 16 | Reconciliation precision: one-sided PO ceilings and normalized duplicates | Complete |
| 17 | Reference-data audit trail for administration mutations | Complete |
| 18 | Operator surface completion: vendor CLI writes and console pagination | Complete |
| 19 | Reference CLI record completion: invoice and purchase-order writes | Complete |
| 20 | Review operator inspection, console filtering, and session lifecycle | Complete |
| 21 | Stale invoice detection rule (ADR 0028) | Complete |
| 22 | Future invoice date detection rule (ADR 0029) | Complete |
| 23 | Duplicate line item detection rule (ADR 0030) | Complete |
| 24 | Non-positive invoice total detection rule (ADR 0031) | Complete |

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
- `veridoc-evaluate` CLI entry point producing machine-readable and Markdown
  decision reports from a corpus manifest; and
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

## Phase 13: evaluation remediation through corpus expansion

Status: complete (design in
[ADR 0024](decisions/0024-expand-synthetic-corpus-to-slice-minimums.md)).

Goal: remediate the Phase 11 `conditional_go` decision
([evaluation report](evaluation-report.md)), whose only blocking condition is
insufficient sample size across every slice (`eng` 2/10, `ara` 1/10,
`clean` 2/10, `noisy` 1/10, `standard` 2/10, `dense` 1/10). Phase 13 expands
the deterministic synthetic benchmark corpus from 3 to 20 documents so every
preregistered slice value — language, quality, layout, and the protocol's
fourth dimension, page count, which the runner must start bucketing — meets
the preregistered minimum of 10 samples.

Planned deliverables:

- one focused ADR recording the corpus-expansion construction method and
  slice-balance rationale;
- page-count (`single`/`multi`) slice bucketing in the deterministic runner,
  matching the four dimensions the protocol already preregisters;
- eight new `eng`/`clean`/`standard` documents (four single-page, four
  multi-page) and nine new `ara`/`noisy`/`dense` documents (four single-page,
  five multi-page), each with complete ground truth (fields, line items,
  expected findings, expected verdict, OCR transcript);
- only committed deterministic construction: Latin lines rendered with the
  Pillow default font, Arabic content composed from the pixel-verified
  `doc_003` rendering, noisy variants via deterministic Pillow transforms,
  dense variants via compact multi-column layouts, and multi-page PDFs via
  embedded page images or text; no new runtime or fixture dependencies;
- a `veridoc-synthetic-benchmark-v2` manifest with SHA-256 digests, slice
  tags, and synthetic license/provenance records, validated by the existing
  manifest checker;
- corpus validity tests proving slice minimums, ground-truth arithmetic
  self-consistency, transcript coverage, and manifest integrity; and
- a fake-harness benchmark run over the expanded corpus proving the runner,
  slice aggregation, and report rendering stay green end to end.

Acceptance criteria:

- every slice value holds at least 10 documents and the manifest validates;
- the full quality gate passes (tests, coverage floor, lint, format, types,
  lockfile, distribution, smoke);
- the fake-harness benchmark exits 0 with every slice marked sufficient; and
- roadmap, changelog, testing guide, fixture guide, runbook, and release
  evidence match the delivered corpus.

Explicit non-goals: changing preregistered thresholds, tuning against the
corpus, any product behavior or endpoint change, retention/purge work, and
the Tesseract-measured re-run with live providers — that measured
re-verification and the resulting go/no-go update execute in the
Tesseract-equipped operator environment as Phase 14, using
the runbook procedure Phase 13 documents.

## Phase 14: measured re-verification and readiness decision update

Status: planned; blocked on a Tesseract-equipped operator environment.

Goal: convert the Phase 13 remediation corpus into an updated readiness
decision by running the frozen protocol with real Tesseract OCR
(`eng` + `ara` trained data) and the evaluated provider identity, then
recording the resulting go/no-go report. The runbook documents the exact
operator procedure. No implementation work is expected; entry requires the
equipped environment plus the named business, security, privacy,
operations, and quality owners from the Phase 11 entry criteria.

## Phase 15: auditor evidence export for review cases

Status: complete (design in
[ADR 0025](decisions/0025-auditor-evidence-export-for-review-cases.md)).

Goal: complete the audit half of the Phase 9 review/audit workflow. Cases
are immutable and digest-verified but only visible through the API and
console; no artifact exists that an auditor can take away and verify
independently. Phase 15 adds a digest-bound evidence bundle per case —
snapshot, ordered events, schema versions, and export metadata — verifiable
offline without store access, served through an authenticated case route,
the `veridoc-review` CLI, and a console download control.

Planned deliverables:

- one focused ADR recording the bundle format, offline verification
  semantics, and trust bounds;
- a review-domain evidence module that builds bundles from canonical case
  detail and verifies them offline (canonical digest, snapshot digest,
  event-chain continuity, version monotonicity), with typed safe errors;
- an authenticated `GET /review/cases/{case_id}/evidence` route mirroring
  the case-detail authorization and not-found contract;
- `veridoc-review export` and `veridoc-review verify-bundle` CLI
  subcommands with safe exit codes;
- a console download control rendered with DOM text nodes only;
- tamper-evident tests (snapshot edits, dropped/reordered events, digest
  changes all fail verification), route auth/404 tests, CLI tests, and
  console markup tests; and
- distribution and smoke registration for the new module and route.

Acceptance criteria:

- an untampered bundle verifies offline with no store access, and every
  tamper class fails verification;
- export requires the same authentication as case detail; unknown cases
  return the existing not-found contract;
- the CLI export and the route return identical bundles for one case;
- the full quality gate passes; and
- API, architecture, runbook, testing guide, changelog, and release
  evidence match the delivered behavior.

Explicit non-goals: PDF rendering of bundles, redacting case content for
auditors (bundles carry the case as-is; handling rules are documented),
retention/purge behavior, batch export, and any change to case
immutability or the append-only event log.

Phase numbering note: Phase 15 implements while Phase 14 awaits its
environment because the measured re-run needs Tesseract plus live
providers, neither of which this development environment provides. Phase
14 remains planned and unblocked the moment the equipped environment is
available; nothing in Phase 15 changes its entry criteria or procedure.

## Phase 16: reconciliation precision

Status: complete (design in
[ADR 0026](decisions/0026-one-sided-po-ceilings-and-normalized-duplicates.md)).

Goal: remove systematic false-positive findings without losing fraud
recall. Two verified precision gaps: invoice numbers compare verbatim, so
OCR/provider variants (`INV-001` vs `inv 001`) of one invoice evade the
duplicate check while stored verbatim; and purchase-order totals and line
quantities compare exactly, so every routine partial invoice against a PO
flags high-severity. Phase 16 canonicalizes invoice-number identity and
turns PO matching into authorization ceilings: billing at or under the
authorized amount is routine, billing above it is review-worthy.

Planned deliverables:

- one focused ADR recording the fraud-model reasoning (why one-sided
  ceilings lose no over-billing recall) and normalization bounds;
- a canonical invoice-number normalizer (NFKC, dash-folding, whitespace
  removal, casefold) with unit tests;
- duplicate detection over the normalized form for the vendor history,
  keeping the `duplicate_invoice_number` finding type and recording both
  the observed and stored forms;
- one-sided PO total and line-quantity rules (flag only invoiced amounts
  above the authorized values; unit prices stay exact; the redundant PO
  line-total comparison goes away);
- a cumulative PO ceiling rule over the already-loaded vendor history
  (prior same-currency invoices against the same PO plus the current
  total must not exceed the PO total), wired through the verification
  service without new repository methods; and
- updated PO/duplicate tests for the new semantics plus new variant,
  one-sided, and cumulative-ceiling tests.

Acceptance criteria:

- verbatim-identical invoices still flag exactly as before;
- normalized variants, partial invoices, and split over-billing behave per
  the ADR with dedicated tests;
- unit-price changes still always flag;
- the full quality gate passes; and
- architecture, changelog, and release evidence match the new semantics.

Explicit non-goals: unit-price tolerance, currency conversion, goods
receipts, retention/purge, batch intake, threshold changes, new finding
types, and any change to arithmetic, vendor-registry, or history rules.

## Phase 17: reference-data audit trail

Status: complete (design in
[ADR 0027](decisions/0027-append-only-admin-audit-log.md)).

Goal: close the accountability gap around the fraud trust anchor. Phase 12
made vendor bank accounts and tax IDs deterministic reconciliation inputs,
but every reference-data mutation (invoice, purchase-order, and vendor
CRUD plus bulk import) executes without recording what changed, when, or
under which request. Under the Phase 10 threat model an administration
credential guess that rewrites a vendor's remit-to account leaves no trace
beyond an updated timestamp. Phase 17 records an append-only audit entry
per mutated record with server timestamp, request correlation ID,
operation, record identity, and canonical before/after images.

Planned deliverables:

- one focused ADR recording the entry schema, shared-token attribution
  limits, post-commit ordering, and non-goals;
- forward-only migration 6 creating the `admin_audit_log` table with
  lookup indexes, plus schema and maintenance validation for its rows;
- bounded audit entry/page models and repository record/list operations on
  the administration protocol, implemented by the SQLite adapter;
- route integration writing exactly one entry per created, updated,
  deleted, or imported record, carrying the request's `X-Request-ID`;
- a `veridoc-reference audit-log` read command with bounded filters and
  pagination; and
- migration, round-trip, pagination, malformed-row, backup/restore, and
  per-route request-linkage tests.

Acceptance criteria:

- every invoice, purchase-order, and vendor create, update, delete, and
  import writes exactly one entry per record with the calling request's
  correlation ID and canonical before/after images;
- malformed audit rows fail maintenance validation like any other
  persisted row;
- backup and restore preserve the log with the database that owns it;
- the full quality gate passes; and
- architecture, API, data-and-security, changelog, and release evidence
  match the delivered behavior.

Explicit non-goals: per-actor attribution (impossible under the shared
administration token — entries record the token-holder role only),
audit-log integrity digests beyond SQLite file controls, automated
retention/purge of the log, an HTTP read route, dry-run logging (dry runs
write nothing), and any change to mutation semantics or conflict behavior.

## Phase 18: operator surface completion

Status: complete (routine completion of existing surfaces, no ADR required).

Goal: finish two operator surfaces left half-built. The `vendors` CLI
group manages vendor master data but cannot create or update records,
forcing scripted onboarding through raw API calls; and the review console
case list hardcodes `limit=50` with no paging, hiding every older case.
Phase 18 adds JSON-file vendor add/update commands mirroring the import
record schemas and previous/next pagination to the console case list.

Planned deliverables:

- `veridoc-reference vendors add --input vendor.json` and
  `veridoc-reference vendors update --record-id <id> --input
  vendor-update.json`, validated through the existing bounded
  `VendorRecordInput`/`VendorRecordUpdate` schemas with safe CLI errors,
  conflict reporting, and audit-trail entries carrying generated request
  identifiers;
- audit entries for the existing `vendors delete` command, which currently
  bypasses the Phase 17 trail by calling the repository without a context;
- console previous/next pagination over the existing bounded
  offset/limit listing, rendered with DOM text nodes only; and
- CLI contract tests (add/update/conflict/invalid-file), console markup
  tests, and corrected vendor CLI documentation (the guide shows
  positional arguments the parser never accepted).

Acceptance criteria:

- scripted vendor onboarding and correction work end to end through the
  CLI, including conflict and invalid-input behavior;
- console pages beyond the first fifty cases with working previous/next
  controls and no `innerHTML`;
- the full quality gate passes; and
- development guide, changelog, and release evidence match the delivered
  behavior.

Explicit non-goals: invoice/purchase-order CLI record commands, vendor
delete behavior changes, case search or filtering beyond pagination,
session management commands, and any API, schema, or threshold changes.

## Phase 19: reference CLI record completion

Status: complete (routine completion of the Phase 18 pattern, no ADR required).

Goal: complete file-based reference-data writes in the operator CLI.
Phase 18 gave the `vendors` group add/update/delete; invoices and
purchase orders — equally file-shaped reference facts — remain API-only,
forcing scripted onboarding through raw HTTP calls. Phase 19 adds
`invoices` and `purchase-orders` groups with `add`, `update`, and `delete`
subcommands over the same bounded JSON schemas, the same audit-trail
contexts, and the same safe CLI errors. Listing and inspection stay
API-side operations.

Planned deliverables:

- `veridoc-reference invoices add --input` / `update --record-id --input` /
  `delete --record-id` and the same three `purchase-orders` commands, with
  bounded JSON reads, schema validation, conflict reporting, and
  per-command audit contexts carrying generated request identifiers;
- CLI contract tests per entity (add/update/delete/conflict/invalid-file/
  missing-record) proving audit entries link each mutation; and
- development-guide CLI documentation, changelog, and release evidence.

Acceptance criteria:

- scripted invoice and purchase-order onboarding, correction, and removal
  work end to end through the CLI;
- every CLI mutation writes exactly one audit entry;
- the full quality gate passes; and
- documentation matches the delivered commands.

Explicit non-goals: CLI listing or inspection for invoices and purchase
orders (API operations), bulk CLI import (the API import route covers
batches), session management commands, and any API, schema, threshold, or
finding changes.

## Phase 20: review operator inspection, console filtering, and session lifecycle management

Status: complete (routine completion of operator and review surfaces, no ADR required).

Goal: complete the operator and reviewer surfaces for the review subsystem.
Currently, operators on the server have no CLI commands to inspect cases or
manage review sessions (`cases list`, `cases get`, `sessions list`, `sessions
revoke`, and `sessions prune` are absent from `veridoc-review`), expired sessions
accumulate without maintenance pruning, and the review console lacks UI filter
controls for case status and assignee even though the underlying API route supports
them. Phase 20 adds case inspection and session lifecycle subcommands to `veridoc-review`,
integrates session pruning into automated deployment maintenance (`veridoc-backup`),
and adds safe DOM-based status and assignee filtering to the review console.

Planned deliverables:

- `ReviewSessionSummary` and `SessionPage` domain models, plus `list_sessions`,
  `revoke_actor_sessions`, and `prune_sessions` protocol methods implemented on
  `SQLiteReviewRepository`;
- `veridoc-review cases list` with bounded `--status`, `--assignee-id`, `--offset`,
  and `--limit` options, and `veridoc-review cases get --case-id <id>` formatting
  snapshot metadata, extraction summary, findings, and event history;
- `veridoc-review sessions list` with `--actor-id`, `--active-only`, `--offset`,
  and `--limit` options, `veridoc-review sessions revoke` with `--digest` or `--actor-id`,
  and `veridoc-review sessions prune` with `--older-than-days`;
- session pruning integration in `veridoc-backup` (`run_deployment_maintenance`)
  with `--session-retention-days`;
- status and assignee filter controls in the review console UI with safe DOM text node
  construction (no `innerHTML`);
- contract tests covering case inspection, session queries/revocation/pruning,
  CLI commands, maintenance integration, and console DOM safety; and
- updated development guide, runbook, architecture notes, and release evidence.

Acceptance criteria:

- operators can list and inspect review cases from `veridoc-review` with bounded output;
- operators can list, revoke, and prune review sessions from `veridoc-review`;
- deployment maintenance prunes expired sessions based on configured retention;
- review console filters cases by status and assignee without `innerHTML`;
- the full quality gate passes; and
- documentation matches the delivered behavior.

Explicit non-goals: case editing or CLI decision making (decisions require human
review workflow via console or authenticated API), remote identity provider integration,
retention/purge of case records (ADR 0010), and any API, schema, or threshold changes.

## Phase 21: stale invoice detection

### Objective

Add a deterministic `stale_invoice` verification rule to catch backdated or
resubmitted invoices that the existing rule set cannot detect without a vendor
history or purchase-order anchor.

### Problem

The verification layer has no check for invoice age relative to the processing
date.  An invoice dated more than 90 days ago with no purchase-order reference
and a positive total is a meaningful fraud indicator: it may have been backdated
to evade controls, or may be a resubmission of a previously paid invoice whose
number was altered to evade duplicate detection.  The existing rules handle
arithmetic, PO ceilings, duplicate numbers, and vendor-history anomalies, but
none of them catch a stale, anchor-free, positive-total invoice.

### Decision summary

See [ADR 0028](decisions/0028-stale-invoice-detection.md).  The rule fires when
`invoice_date < today - 90 days` and `purchase_order_number` is absent or blank
and `total > 0`.  Severity is `medium` (warrants human review; not proof of
fraud alone).  The reference date is injected as a parameter for determinism.
PO-anchored and zero-total invoices are explicitly excluded.  No migration, new
repository method, or threshold-calibration change is required.

### Deliverables

- `stale_invoice` added to `FindingType` in `veridoc.verification.models`;
- `check_invoice_staleness()` pure function in `veridoc.verification.staleness`
  with injected reference date;
- `VerificationService.verify()` calls `check_invoice_staleness` after
  `check_arithmetic`;
- `tests/test_verification_staleness.py` covering all 21 cases: every exclusion
  path, triggering path, boundary condition, parametrized PO suppression, decimal
  accuracy, immutability, and default-date behavior;
- `docs/decisions/0028-stale-invoice-detection.md` (ADR 0028);
- `docs/testing.md` inventory updated;
- `AGENTS.md` updated to reflect all 21 complete phases;
- `CHANGELOG.md` updated.

### Acceptance criteria

- `stale_invoice` appears in `FindingType` and is accepted by `VerificationFinding`;
- the pure function returns exactly one finding for stale invoices meeting all
  conditions and an empty list for every exclusion case;
- `VerificationService` includes staleness findings in its output;
- all 21 staleness tests pass and the full quality gate passes;
- `test_documentation.py` validates the updated test-module inventory;
- no pre-existing test regressions.

## Phase 22: future invoice date detection

### Objective

Add a deterministic `future_invoice_date` verification rule to catch
post-dated or forward-dated invoices whose issue date occurs after the current
processing date.

### Problem

The verification layer checks relative dates within an invoice
(`invoice_date <= due_date`) and historical staleness (`invoice_date < today - 90 days`),
but has no check for invoices dated in the future. In accounts payable operations,
tax compliance (VAT, GST, sales tax), and accounting standards (GAAP, IFRS), an
invoice dated in the future cannot legally be posted or claimed for input tax
deductions prior to its tax point / issue date. Post-dated invoices are classic
indicators of accounting cutoff manipulation, premature billing fraud, or vision/OCR
date extraction errors (such as year hallucination or month-day transposition).
An invoice dated in the future previously evaded all verification rules and yielded
an unearned `clear` verdict.

### Decision summary

See [ADR 0029](decisions/0029-future-invoice-date-detection.md). The rule fires when
`invoice_date > today`. Severity is `medium` (warrants human review; not fatal
rejection alone, allowing review of timezone drift or clerical errors). The
reference date is injected as a parameter for determinism (defaulting to UTC today).
Unlike staleness, purchase orders and zero/credit totals do not suppress the check:
a purchase order never authorizes billing in the future, and post-dated credit memos
are equally invalid. No migration or threshold calibration is required.

### Deliverables

- `future_invoice_date` added to `FindingType` in `veridoc.verification.models`;
- `check_future_invoice_date()` pure function in `veridoc.verification.future_dates`
  with injected reference date;
- `VerificationService.verify()` calls `check_future_invoice_date` alongside
  `check_invoice_staleness`;
- `tests/test_verification_future_dates.py` covering all paths: non-triggering
  paths (absent date, today, past dates), triggering paths (tomorrow, far future,
  singular/plural day formatting, total independence, PO independence),
  immutability, default reference date, and service/verdict integration;
- `docs/decisions/0029-future-invoice-date-detection.md` (ADR 0029);
- `docs/testing.md` inventory updated;
- `AGENTS.md` updated to reflect all 22 complete phases;
- `CHANGELOG.md` updated.

### Acceptance criteria

- `future_invoice_date` appears in `FindingType` and is accepted by `VerificationFinding`;
- the pure function returns exactly one finding for post-dated invoices and an
  empty list for current, past, or absent dates;
- `VerificationService` includes future invoice date findings in its output;
- all future date tests pass and the full quality gate passes;
- `test_documentation.py` validates the updated test-module inventory and links;
- no pre-existing test regressions.

## Phase 23: duplicate line item detection

### Objective

Add a deterministic `duplicate_line_item` verification rule to detect repeated
or duplicate line items within a single invoice, preventing double-billing fraud,
data entry duplication, and OCR table extraction artifacts from receiving an
unearned `clear` verdict.

### Problem

The verification layer validates arithmetic consistency (subtotals, tax, discounts,
line-item math, totals), temporal dates (future issue dates, stale invoices, due
date ordering), vendor registry compliance, cross-invoice duplicate invoice numbers,
and historical statistics. However, it previously lacked any intra-invoice check for
duplicate line items.

In accounts payable and invoice processing, duplicate line items represent a major
clerical error and billing fraud pattern:

1. **Double-billing fraud and data entry errors** — an issuer inadvertently or
   intentionally lists the same deliverable, fee, or service multiple times
   on a single invoice. Because the arithmetic engine validates the subtotal as the
   sum of line-item totals (`sum(line_item.total_price) == subtotal`), an invoice
   containing duplicated lines passes arithmetic validation without error.
2. **Vision extraction and OCR artifacts** — vision-language models and OCR layout
   engines occasionally re-read table rows, transcribe overlapping bounding boxes,
   or generate duplicate structured line items from repeated headers or page
   transitions.

An invoice with duplicated lines previously passed arithmetic, temporal, and historical
verification, receiving an unearned `clear` processing verdict unless an external
purchase order happened to be attached or total outliers were triggered. Detecting
duplicate line items within an invoice prevents automated acceptance of double-billed
charges.

### Decision summary

See [ADR 0030](decisions/0030-duplicate-line-item-detection.md). The rule inspects
`invoice.line_items` and computes comparison keys using `line_item_key` from
`veridoc.verification.line_items`, canonicalizing whitespace and letter casing.
When two or more line items share the same key, every occurrence after the first
generates a `duplicate_line_item` finding referencing the initial occurrence index.
Severity is differentiated based on matching depth:
- `high` severity for exact duplicates where both `quantity` and `unit_price` match;
- `medium` severity for partial duplicates where the key matches but `quantity` or
  `unit_price` differs (or is omitted), routing split deliveries to human review.
Comparison source is `"invoice_line_items"`, and deterministic rule is
`"line items within an invoice must be unique by product identifier or description"`.
No migration, repository change, or threshold calibration is required.

### Deliverables

- `duplicate_line_item` added to `FindingType` in `veridoc.verification.models`;
- `check_duplicate_line_items()` pure function in `veridoc.verification.duplicate_line_items`;
- `VerificationService.verify()` calls `check_duplicate_line_items`;
- `tests/test_verification_duplicate_line_items.py` covering all paths: empty/single line
  items, distinct lines, missing identifiers, exact matches (product ID, description),
  casing/whitespace normalization, partial matches (differing quantity, differing unit
  price, missing values), triple duplicates, multiple groups, interleaved lines,
  immutability, service integration, and verdict derivation;
- `docs/decisions/0030-duplicate-line-item-detection.md` (ADR 0030);
- `docs/testing.md` inventory updated;
- `AGENTS.md` updated to reflect all 23 complete phases;
- `CHANGELOG.md` updated.

### Acceptance criteria

- `duplicate_line_item` appears in `FindingType` and is accepted by `VerificationFinding`;
- the pure function returns findings for duplicate line items (high for exact, medium for
  partial) and an empty list for unique line items;
- `VerificationService` includes duplicate line item findings in its output;
- all duplicate line item tests pass and the full quality gate passes;
- `test_documentation.py` validates the updated test-module inventory and links;
- no pre-existing test regressions.

## Phase 24: non-positive invoice total detection

### Objective

Add a deterministic `non_positive_invoice_total` verification rule to detect
invoices with zero or negative total amounts, preventing zero-dollar vouchers,
pro-forma documents, credit notes misclassified as invoices, and negative
billing fraud from receiving an unearned `clear` processing verdict.

### Problem

The verification layer validates arithmetic consistency (subtotals, tax, discounts,
line-item multiplication, totals), temporal dates (future issue dates, stale invoices,
due date ordering), duplicate line items, duplicate invoice numbers, purchase-order
authorization ceilings, and vendor registry compliance. However, it previously lacked
any check ensuring that the invoice total payable is strictly positive.

In accounts payable and invoice processing:

1. **Commercial invoices demand positive payment** — A commercial invoice
   (`document_type="invoice"`) is a demand for payment for goods or services delivered.
   Under standard accounting rules (GAAP, IFRS) and tax regulations, an invoice
   must specify a strictly positive payable total (`total > 0`).
2. **Zero-total invoices (`total == 0`)** — An invoice requesting $0.00 is an
   operational anomaly. It may be an informational delivery slip, pro-forma quote,
   warranty replacement slip, or sample notice erroneously submitted as an invoice.
   Alternatively, it is a frequent vision/OCR extraction defect where the monetary total
   was occluded, blanked, or misparsed as zero. Allowing zero-dollar invoices to clear
   automatically risks marking unfulfilled purchase-order lines as completed or
   polluting accounting registers with zero-value vouchers.
3. **Negative-total invoices (`total < 0`)** — An invoice specifying a negative
   payable balance represents a credit memo, debit adjustment, or refund claim.
   Processing a negative amount through a standard invoice pipeline without dedicated
   credit authorization can corrupt accounts payable balances, generate erroneous
   payment batches, or facilitate unauthorized debit manipulation.

Previously, an invoice with `total <= 0` whose arithmetic balanced (e.g.
`-100.00 + 0 - 0 == -100.00` or `0.00 + 0 - 0 == 0.00`) passed arithmetic validation,
was ignored by staleness checks (`total <= 0`), and was less than any positive
purchase-order ceiling, thereby receiving an unearned `clear` verdict.

### Decision summary

See [ADR 0031](decisions/0031-non-positive-invoice-total-detection.md). The rule inspects
`invoice.total`. When `invoice.total <= Decimal(0)`, exactly one `non_positive_invoice_total`
finding is generated. Severity is differentiated based on financial risk:
- `high` severity for negative totals (`total < 0`), flagging credit notes and billing
  reversals requiring immediate human verification;
- `medium` severity for zero totals (`total == 0`), flagging zero-value vouchers and
  extraction artifacts for review.
Absent totals (`total is None`) and strictly positive totals (`total > 0`) produce no
findings. Comparison source is `"invoice_fields"`, and deterministic rule is
`"invoice.total > 0"`. No migration or external dependency is required.

### Deliverables

- `non_positive_invoice_total` added to `FindingType` in `veridoc.verification.models`;
- `check_non_positive_invoice_total()` pure function in `veridoc.verification.invoice_totals`;
- `VerificationService.verify()` calls `check_non_positive_invoice_total`;
- `tests/test_verification_invoice_totals.py` covering all paths: absent total, positive
  totals, minimal positive, zero totals (standard, integer, multi-decimal, Decimal),
  negative totals (standard, minimal, large), currency preservation, negative zero,
  PO/date/line-item independence, immutability, service integration, and verdict derivation;
- `docs/decisions/0031-non-positive-invoice-total-detection.md` (ADR 0031);
- `docs/testing.md` inventory updated;
- `AGENTS.md` updated to reflect all 24 complete phases;
- `CHANGELOG.md` updated.

### Acceptance criteria

- `non_positive_invoice_total` appears in `FindingType` and is accepted by `VerificationFinding`;
- the pure function returns findings for non-positive totals (high for negative, medium
  for zero) and an empty list for positive or absent totals;
- `VerificationService` includes non-positive invoice total findings in its output;
- all 28 non-positive total tests pass and the full quality gate passes;
- `test_documentation.py` validates the updated test-module inventory and links;
- no pre-existing test regressions.

## Phase 25: non-positive line item detection

### Objective

Add a deterministic `non_positive_line_item` verification rule to detect invoice
line items with zero or negative amounts, unit prices, or quantities, preventing
unauthorized credit lines, rebate deductions, returns, zero-dollar vouchers, and
OCR negative-sign artifacts from receiving an unearned `clear` processing verdict.

### Problem

The verification layer validates arithmetic consistency (subtotals, tax, discounts,
line-item math, totals), temporal dates (future issue dates, stale invoices, due
date ordering), intra-invoice duplicate line items, duplicate invoice numbers,
purchase-order authorization ceilings, vendor registry compliance, and overall
invoice total positivity (`total > 0`, Phase 24). However, it previously lacked
any constraint on the positivity of individual line items within an invoice.

In accounts payable, enterprise ERPs, and auditing standards:

1. **Commercial invoices demand positive line items** — Invoices are instruments
   demanding payment for goods or services delivered. Every commercial line item
   must specify strictly positive values for quantity (`quantity > 0`), unit
   price (`unit_price > 0`), and line amount (`total_price > 0`).
2. **Negative line items (`total_price < 0`, `unit_price < 0`, `quantity < 0`)** —
   Represent unauthorized credit lines, debit deductions, returns, trade-ins, or
   rebate offsets embedded into an invoice without dedicated credit-note
   authorization. Netting negative line items inside standard invoices distorts
   sales tax and VAT calculations (such as when standard-rated and zero-rated items
   are netted), evades purchase-order spend authorization limits, and violates AP
   internal controls requiring separate credit notes. Negative line items also
   frequently arise from OCR vision artifacts where hyphens, bullets, dashes, or
   glyphs are erroneously transcribed as negative signs.
3. **Zero line items (`total_price == 0`, `unit_price == 0`, `quantity == 0`)** —
   Zero-quantity lines (`quantity == 0`) indicate unperformed services or
   placeholder rows billed for payment. Zero unit price or zero line totals
   (`unit_price == 0` or `total_price == 0`) represent promotional free samples,
   zero-dollar warranty inclusions, or vision price dropouts. These require human
   review to verify contractual validity or OCR completeness.

Currently, if an invoice has a positive total (`total > 0`), but contains line
items with negative or zero values whose internal multiplication balances
(for example, `quantity = -2, unit_price = 50.00, total_price = -100.00`, netted
against a positive line item), `check_arithmetic` passes, `check_line_items_subtotal`
passes, `check_non_positive_invoice_total` passes, and the invoice receives an
unearned `clear` processing verdict.

### Decision summary

See [ADR 0032](decisions/0032-non-positive-line-item-detection.md). The rule inspects
each line item in `invoice.line_items`. When observed, non-null values for
`quantity`, `unit_price`, or `total_price` are less than or equal to `Decimal(0)`,
a `non_positive_line_item` finding is generated for that line item. Severity is
differentiated based on financial risk:
- `high` severity if any observed non-positive field is negative (`< 0`), flagging
  credit lines, returns, and billing adjustments requiring human review;
- `medium` severity if all observed non-positive fields are zero (`== 0`), flagging
  zero-value promotional items, placeholder lines, or extraction dropouts.
Absent fields (`None`) are ignored to avoid penalizing unextracted optional fields.
Comparison source is `"invoice_line_items"`, and deterministic rule is
`"line_item.quantity > 0 and line_item.unit_price > 0 and line_item.total_price > 0"`.
No database migration, new repository method, or external dependency is required.

### Deliverables

- `non_positive_line_item` added to `FindingType` in `veridoc.verification.models`;
- `check_non_positive_line_items()` pure function in `veridoc.verification.line_item_amounts`;
- `VerificationService.verify()` calls `check_non_positive_line_items`;
- `tests/test_verification_line_item_amounts.py` covering all paths: empty lines, positive
  lines, missing optional fields, negative total price, zero total price, negative quantity,
  zero quantity, negative unit price, zero unit price, multiple non-positive fields,
  multiple line items, structured details, immutability, service integration, and verdict derivation;
- `docs/decisions/0032-non-positive-line-item-detection.md` (ADR 0032);
- `docs/testing.md` inventory updated;
- `docs/architecture.md` updated;
- `AGENTS.md` updated to reflect all 25 complete phases;
- `CHANGELOG.md` updated;
- `docs/release-evidence.md` completion snapshot.

### Acceptance criteria

1. `non_positive_line_item` appears in `FindingType` and is accepted by `VerificationFinding`.
2. The pure function returns findings for non-positive line items (high for negative, medium
   for zero) and an empty list for positive or absent values.
3. `VerificationService` includes non-positive line item findings in its output.
4. Non-positive line item findings drive the processing verdict to `review_required`.
5. All non-positive line item tests pass and the full quality gate passes without regressions.
6. `test_documentation.py` validates the updated test-module inventory and links.

### Validation plan

- Run focused unit tests for `non_positive_line_item` schema and pure function.
- Run `tests/test_verification_line_item_amounts.py` with comprehensive test cases.
- Run full pytest test suite (1224+ tests).
- Run type check (`uv run mypy`), linter (`uv run ruff check .`), and formatter (`uv run ruff format --check .`).
- Run documentation and link validation (`uv run pytest tests/test_documentation.py`).

### Exclusions

- Modifying `InvoiceLineItem` schema or database tables (domain and storage schemas remain unchanged).
- Modifying extraction prompt or OCR logic (verification operates purely on deterministic extraction outputs).
- Modifying evaluation benchmark thresholds or frozen metrics.
- CLI or API route alterations (existing processing endpoints automatically surface verification findings).

### Task list

1. Update `docs/roadmap.md` with Phase 25 scope and create `docs/PROGRESS.md`.
2. Record Phase 25 Architecture Decision Record (ADR 0032) and update decisions index.
3. Add `non_positive_line_item` to `FindingType` union in `veridoc.verification.models` and add model test.
4. Implement pure deterministic function `check_non_positive_line_items` in `veridoc.verification.line_item_amounts`.
5. Integrate `check_non_positive_line_items` into `VerificationService.verify()`.
6. Add comprehensive test suite in `tests/test_verification_line_item_amounts.py`.
7. Update `docs/testing.md` test inventory.
8. Update `docs/architecture.md`.
9. Update `AGENTS.md`.
10. Update `CHANGELOG.md`.
11. Update `docs/roadmap.md` active links and record completion snapshot in `docs/release-evidence.md`.

## Approval rule

Phases 0 through 13 and Phases 15 through 25 are complete. Phase 14 is
planned but environment-blocked. Before any later phase, inspect the
repository, run the existing suite, present the implementation and commit
plan, identify documentation changes, and wait for explicit approval. The
same rule applies to any future phase's approval.
