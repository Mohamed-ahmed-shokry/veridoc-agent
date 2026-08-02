# Project Roadmap

Veridoc Version 1 invoice and purchase-order reconciliation is complete through
Phase 6. Phase 7 release-engineering hardening is also complete. Later phases
are planning boundaries only and require separate approval before implementation.

## Phase status

| Phase | Scope | Status |
| --- | --- | --- |
| 0-6 | Version 1 application, processing workflow, integration, and documentation | Complete |
| 7 | Release engineering and reproducible quality gates | Complete |
| 8 | Controlled reference-data administration | Planned; not approved |
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
  package build, and installed-wheel smoke testing;
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
7. Add package-content and isolated-wheel verification.
8. Add the Version 1 changelog.
9. Synchronize project and operating documentation.
10. Run and record the complete Phase 7 completion gate.

Phase 7 explicitly excludes Docker/container choices, cloud deployment,
authentication, database administration endpoints, review persistence, and a
license selection. Each changes operational or legal scope and belongs to a
separately approved phase or decision.

## Phase 8: controlled reference-data administration

Candidate scope:

- authenticated local administration boundary for fictional/approved invoice
  history and purchase orders;
- validated import with dry-run and atomic replacement behavior;
- explicit schema migrations and backup/restore procedures;
- conflict, provenance, and retention metadata; and
- safe list/add/update/delete APIs that never expose document bodies.

This phase must select an authentication model and migration strategy before
implementation. SQLite remains behind `InvoiceRepository` unless evidence
supports a new adapter.

## Phase 9: persistent review and audit workflow

Candidate scope:

- persistent review cases linked to immutable processing results;
- reviewer assignment and status transitions;
- explicit approve/reject/escalate decisions with reasons;
- append-only audit events and retention policy; and
- an authenticated review interface that cannot mutate canonical findings.

This phase must define actors, authorization rules, retention, and the legal
meaning of a review decision. A `clear` processing verdict must remain distinct
from human approval.

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

Phase 7 is complete, and no later phase is approved. Before any later phase,
inspect the current repository, run the full existing gate, present the exact
implementation and atomic commit plan, identify data/security decisions, and
wait for explicit user approval.
