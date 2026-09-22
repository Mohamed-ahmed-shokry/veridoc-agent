# Changelog

All notable project changes are recorded here. The project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) categories and will use
semantic versions for tagged releases.

## [Unreleased]

### Added

- Phase 15 auditor evidence export for review cases:
  - Architecture Decision Record 0025 documenting the digest-bound bundle
    format, offline verification semantics, and auditor handling bounds.
  - `veridoc.review.evidence` domain module building canonical bundles from
    case detail and verifying them offline (snapshot digest, event-chain
    continuity, transition legality, bundle digest) with typed safe errors.
  - Authenticated `GET /review/cases/{case_id}/evidence` route mirroring the
    case-detail authorization and not-found contract.
  - `veridoc-review export` and `veridoc-review verify-bundle` maintenance
    subcommands with safe exit codes.
  - Console evidence-bundle download control rendered with DOM text nodes
    only.
  - Tamper-evident, route, CLI, console-markup, distribution, and smoke
    coverage for the new module and route.
- Phase 13 evaluation remediation through corpus expansion:
  - Architecture Decision Record 0024 documenting the deterministic corpus
    construction method and exact slice-balance rationale.
  - Page-count (`single`/`multi`) slice bucketing in the deterministic
    evaluation runner, matching the fourth dimension the preregistered
    protocol already requires.
  - Seventeen new synthetic benchmark documents with complete ground truth:
    eight `eng`/`clean`/`standard` invoices and nine `ara`/`noisy`/`dense`
    invoices, each with varied fictional vendors, numbers, dates, amounts,
    and line items, including intentional total mismatches expecting
    `invoice_total_mismatch` with `review_required` verdicts.
  - `veridoc-synthetic-benchmark-v2` manifest with SHA-256 digests,
    synthetic license and provenance records, and exactly 10 samples per
    language, quality, layout, and page-count slice value.
  - Corpus validity tests proving slice minimums, ground-truth arithmetic
    self-consistency, transcript coverage, manifest integrity, and ingestion
    processability of every document.
  - Committed deterministic construction script
    (`tests/fixtures/corpus/make_corpus_v2.py`) and fixture-guide corpus
    rules; re-running it yields byte-identical files.
  - Runbook procedure for the Tesseract-measured re-run that converts the
    remediation corpus into an updated readiness decision.
- Phase 12 authoritative vendor registry, entity resolution, and bank reconciliation:
  - Architecture Decision Records 0021-0023 documenting vendor master schema, cascading multi-attribute entity resolution, and deterministic remit-to bank account/tax ID reconciliation rules.
  - Strict vendor master domain schemas (`veridoc.vendors.models`) for `VendorEntity`, `VendorBankAccount`, `VendorTaxId`, `VendorResolutionResult`, and `VendorMatchConfidence`.
  - SQLite Migration 5 establishing `vendors`, `vendor_aliases`, `vendor_bank_accounts`, and `vendor_tax_ids` tables with unique indexes, foreign key constraints, and schema validation.
  - Vendor repository protocol `VendorRepository` and SQLite persistence implementation in `veridoc.persistence.sqlite`.
  - Deterministic cascading entity resolution engine (`veridoc.vendors.resolution.resolve_vendor`) matching across tax IDs, bank accounts, canonical keys, aliases, and bounded token similarity (>= 0.85).
  - Deterministic verification rules in `veridoc.verification.vendor_rules` for `unregistered_vendor`, `suspended_vendor`, `vendor_bank_account_mismatch`, and `vendor_tax_id_mismatch`.
  - Integration of `vendor_resolution` into `ProcessingResult`, processing graph, and service.
  - Authenticated reference-data administration API (`POST/GET/PUT/DELETE /admin/reference-data/vendors`) and batch JSON import support.
  - `veridoc-reference vendors` CLI subcommands (`list`, `get`, `delete`).
  - Authenticated review console integration displaying vendor resolution badges and bank account mismatch warnings safely without `innerHTML`.
- Phase 11 evaluation, performance, and production-readiness decision:
  - Architecture Decision Records 0018-0020 documenting the preregistered evaluation protocol, observable provider identity capture with drift triggers, and corpus manifest governance.
  - Strict evaluation domain schemas (`veridoc.evaluation.models`) for corpus manifests, test slice definitions, evaluation runs, slice summaries, and decision reports.
  - Versioned corpus manifest validator (`veridoc.evaluation.manifest`) enforcing SHA-256 integrity, path safety, and license/provenance policies without committing sensitive documents.
  - Slice-level metrics for OCR character and word error rates (CER/WER) in `veridoc.evaluation.metrics.ocr`.
  - Field-level extraction exact-match, normalized token F1, and evidence grounding metrics in `veridoc.evaluation.metrics.extraction`.
  - Verification rule confusion matrices (TPR/TNR/FPR/FNR) and verdict concordance metrics in `veridoc.evaluation.metrics.verification`.
  - Explanation guardrail violation, fallback necessity, and factual fidelity metrics in `veridoc.evaluation.metrics.explanation`.
  - Runtime artifact and provider identity capture (`veridoc.evaluation.identity`) tracking git commit, dependencies, OCR assets, and LLM parameters with hard/soft drift classification.
  - Deterministic evaluation runner (`veridoc.evaluation.runner`) calculating slice performance and Wilson score confidence intervals (95% confidence) for sample uncertainty.
  - Decision evaluator (`veridoc.evaluation.decision`) mapping observed slice metrics against preregistered thresholds to yield `go`, `conditional_go`, or `no_go` decision reports.
  - Maintenance and benchmark CLI `veridoc-evaluate` supporting `run`, `benchmark`, and `check-drift` operations.
  - Preregistered evaluation protocol in `docs/evaluation-protocol.md` and baseline synthetic benchmark decision report in `docs/evaluation-report.md`.
  - Synthetic evaluation corpus benchmark fixtures in `tests/fixtures/corpus/`.
- Phase 10 deployment and operational security hardening:
  - Reproducible container packaging (`Dockerfile`, non-root user `veridoc` UID 10001, pinned Debian base `python:3.12.12-slim-bookworm`, multi-language `tesseract-ocr-eng` and `tesseract-ocr-ara` trained data).
  - Runtime secret injection via `scripts/entrypoint.sh` avoiding credential persistence in images or diagnostics (ADR 0014).
  - Environment-specific operations, deployment, and incident runbook in `docs/runbook.md`.
  - Deployment readiness probe `GET /ready` verifying OCR executable, configured language assets in `TESSDATA_PREFIX` (`eng` and `ara`), and database schemas for both reference and review stores (ADR 0017).
  - Operational-only telemetry registry and structured, redacted JSON export at `GET /metrics` (ADR 0016, ADR 0017).
  - Deployment rate limiting (`RateLimiter`) and request concurrency limiting (`ConcurrencyLimiter`) middleware with safe 429 and 503 error responses.
  - Pre-decode upload scanning and encrypted quarantine storage abstraction (`QuarantineStore`, `ClamAVScannerStub`, `ScanStatus`) isolating suspicious files before parsing (ADR 0012, ADR 0016).
  - Automated deployment maintenance and backup CLI `veridoc-backup` with retention policy preserving the 2 most recent verified backups per store and automatic disposal of expired quarantine records (ADR 0015).
  - Architecture Decision Records 0011-0017 documenting containerization, threat modeling, local identity with proxy TLS, secret injection, encrypted storage, upload scanning, and operational telemetry.
  - Container build step in `.github/workflows/ci.yml`.
- A per-actor authenticated, persistent review workflow (Phase 9): session
  cookies (`HttpOnly`/`Secure`/`SameSite=Strict`), double-submit CSRF and
  exact-origin protection, and two roles (`reviewer`, `review_admin`).
- Immutable, schema-versioned, digest-verified per-case processing snapshots
  with an append-only, ordered event history, in a dedicated review SQLite
  store independent of reference-data persistence.
- `POST /review/cases`, running the same processing pipeline as `/process`
  and atomically persisting its result as a new case's initial snapshot and
  event.
- Bounded, filtered case listing and detail routes
  (`GET /review/cases`, `GET /review/cases/{case_id}`).
- Claim/assign/reassign, escalate, and terminal-decision mutation routes,
  each guarded by an `expected_version` optimistic-concurrency check and an
  `Idempotency-Key`; a reassignment requires a non-empty reason.
- A build-free authenticated review console at `GET /review/console`
  rendering login, the case list, per-case evidence, the event timeline, and
  every action entirely through DOM text nodes, never `innerHTML`.
- Numbered forward-only review-store migrations, structural schema
  validation, and a `veridoc-review` online-backup/stopped-service-restore
  maintenance entry point, mirroring the reference-data tooling
  independently.
- ADRs 0008-0010 recording the actor/session/CSRF design, the immutable
  versioned review-record design, and the deferred automated
  retention/purge decision.
- Detailed, approval-gated implementation plans for candidate Phases 10 and
  11, including entry criteria, atomic delivery order, verification, and exit
  criteria.
- Phase 7 roadmap and explicit approval boundaries for later candidate phases.
- Strict mypy checks for the production package.
- A 90% branch-aware coverage floor, established from a 93.35% baseline.
- GitHub Actions checks for locked sync, audit, lint, format, types, coverage,
  builds, package validation, and separate isolated wheel/source-distribution
  smokes.
- Locked dependency-vulnerability and distribution-metadata tooling.
- Safe wheel and source-distribution content validation.
- Bearer-authenticated invoice and purchase-order reference-data administration.
- Strict provenance/retention schemas and bounded paginated CRUD endpoints.
- Atomic JSON imports with reject, skip, replace, and dry-run conflict policies.
- Numbered forward-only SQLite migrations with legacy metadata backfill.
- Online SQLite backup and stopped-service validated atomic restore commands.
- A `veridoc-reference` maintenance entry point and Phase 8 focused tests.
- A configurable, validated per-page Tesseract timeout.
- Central SQLite schema-invariant validation shared by repository startup,
  backup, and restore.
- Pytest-enforced local Markdown link and documented test-module inventory
  consistency checks.
- The project now requires the validated uv 0.9.13 toolchain locally and in CI.
- Focused coverage for request-body limits, upload/dependency ordering,
  concurrent migrations, artifact safety, and uniform-history comparisons.

### Changed

- Reference-data administration routes (`/admin/reference-data/*`) now strictly
  enforce local loopback caller origin, returning HTTP 503 `admin_authentication_unavailable`
  to remote clients before inspecting credentials or resolving storage (ADR 0013).
- Distribution validation and smoke testing now require `deployment/maintenance.py`,
  `evaluation/cli.py`, and the `veridoc-backup` and `veridoc-evaluate` console script entry points.
- Typed graph builders, provider inputs, numeric calculations, decoder values,
  SQLite insert identifiers, and request middleware now satisfy the strict gate.
- Package metadata now uses `README.md` as its Markdown long description.
- Reference persistence initializes through the migration ledger and closes all
  SQLite connections explicitly.
- Administration canonicalizes vendor keys consistently across stored records
  and invoice or purchase-order list filters.
- Verification falls back to a usable vendor name when an extracted vendor
  identifier cannot be normalized, preserving repository-backed checks.
- Every repository write path applies the same canonical vendor-key and bounded
  record schema before persisting reference facts.
- Repository reads revalidate stored facts and metadata, mapping malformed or
  noncanonical rows to the safe reference-data availability boundary.
- Fictional PDF fixtures suppress generated trailer IDs for reproducible bytes.
- Distribution validation now requires Phase 8 modules and both console scripts.
- Upload decoding/inspection, OCR, multimodal provider-payload encoding,
  reference-import parsing, and SQLite import work run outside async request
  loops, and validation completes before external service construction.
- Request-scoped extraction and explanation provider clients close
  deterministically after dependency teardown.
- Extraction and explanation provider calls have a bounded 120-second
  application deadline; extraction maps expiry to `extraction_unavailable` and
  explanation expiry or malformed drafts use deterministic fallback guidance.
- Invalid Tesseract language or timeout settings map to the typed, correlated
  `ocr_unavailable` response on every document endpoint.
- First-time migrations and record updates acquire SQLite write locks before
  reading state that governs their writes.
- Already-current repository initialization validates read-only, avoiding a
  needless write reservation during normal requests.
- Repository initialization validates the final schema before committing its
  migration transaction, so rejected upgrades leave the database unchanged.
- Migration 4 adds required unique parent/position indexes for invoice and
  purchase-order line items, enforcing order integrity and serving child reads.
- Compound SQLite reads use one snapshot for coherent pagination and line items
  during concurrent administration writes.
- Administrative pagination offsets are bounded to SQLite's signed 64-bit
  range before query binding.
- Purchase-order reconciliation consumes matching duplicate line references
  one-to-one.
- Historical-total checks require a known invoice currency before selecting
  same-currency reference data.
- Line-item occurrence and statistical checks require a known invoice currency
  before selecting comparable reference data.
- Online backup preserves the live source and the published snapshot at their
  original schema version while validating a disposable migrated copy.
- Backup and restore validation copies commit migrations only after the final
  structural schema validator succeeds in the same transaction.
- Ruff targets Python 3.12 explicitly; pytest rejects unknown configuration and
  markers; CI scans tracked whitespace and verifies critical installed routes,
  entry points, and version parity.
- CI pins the checkout action by full release SHA, disables persisted checkout
  credentials, and pins the validated uv CLI version.
- Extracted the shared OCR/extraction/processing dependency composition and
  the validated-upload dependency into `veridoc.processing.dependencies` and
  `veridoc.ingestion.dependencies`, so `/process` and the new review routes
  compose the identical dependency graph instead of each maintaining its own.
- Distribution validation now also requires the Phase 9 review router and
  console-page modules and the `veridoc-review` console script; the
  installed-distribution smoke check now recursively discovers routes
  registered through `include_router`, including through an opaque wrapper
  some Starlette versions use, rather than only reading top-level routes.

### Fixed

- Review idempotency digests are bound to the target case, creation retries are
  resolved before processing runs again, mutation events retain their key, and
  every replay returns the originally recorded case version rather than later
  case state.
- `app.py` retained dead-code duplicate copies of the OCR/extraction
  dependency functions after they were extracted into
  `veridoc.processing.dependencies`; the duplicates silently shadowed the
  imports of the same name, so `/process`, `/ocr`, and `/extract` were
  quietly resolving a second, divergent copy of the dependency graph instead
  of the shared one the review routes use. Removed the duplicates.

### Security

- Administration validates a 32-256 character local token and compares
  fixed-length credential digests in constant time before resolving the
  reference database.
- Administration create/update JSON bodies and raw imports are limited to 1 MiB
  before parsing; imports allow 500 records and 200 line items per record.
- Request-validation responses use the generic safe `invalid_request` envelope
  without echoing submitted fields or values.
- Backup and restore reject incomplete current schemas and replace destinations
  only after structural and persisted-row semantic checks succeed.
- Document/import multipart bodies are bounded before parsing, including under
  ASGI mounts or root paths; PDFs have a cumulative raster-pixel limit;
  normalized vision inputs enforce an aggregate byte limit during PNG encoding;
  Tesseract execution is time-bounded; malformed OCR engine results use the
  safe processing error; and invalid OCR confidence values are excluded from
  aggregates.
- PDF open, page-decoding, and geometry failures use the safe malformed-document
  response and still close the decoder document.
- Extracted decimals are bounded before arithmetic, while evidence pages and OCR
  spans must be grounded in the current request before verification.
- Unexpected server failures retain safe request correlation, provider keys are
  redacted from settings representations, and artifact checks reject Windows
  drive/backslash paths, colliding names, links, and special archive members.
- Backup and restore validate foreign-key integrity and schema constraints,
  including declared column types, reject triggers and semantically invalid
  facts or metadata, and refuse WAL, SHM, or rollback-journal destination
  sidecars; restore also refuses those sidecars beside its source backup; and
  neither operation may write to a source-sidecar path.
- Backup and restore open validated source databases in no-create mode, so a
  source removed concurrently cannot be recreated empty or replace good data.
- Review actor credentials are compared against stored digests with a
  constant-time scan over every configured actor that does not short-circuit
  on the first match, so response timing does not reveal which actor (if
  any) a presented credential belongs to.
- Every review mutation resolves session, CSRF, and origin dependencies
  before any repository or processing dependency, so a rejected request
  never causes an untrusted document to reach OCR, extraction, the
  reference database, or a review-store write.
- Review login credentials and mutation CSRF/origin checks now fail before
  review storage resolves; missing session cookies also short-circuit protected
  reads and logout. The console clears the credential field after every login
  attempt.
- Review assignment, escalation, and decision JSON bodies are bounded to 32 KiB
  before parsing or authentication, including streamed requests.
- Review configuration rejects non-origin URL variants and database hard-link
  aliases, while schema and maintenance validation now verify exact columns,
  query indexes, event transitions, current assignees, idempotency rows, and
  session rows.
- Reference schema validation requires exact managed columns and both invoice
  lookup indexes; both stores reject unexpected unique indexes that could
  change valid-write behavior.
- Review case creator/timestamps must agree with their event chain, event times
  cannot move backward, and maintenance binds every idempotency row to its
  exact result event before publishing a backup or restored database.
- Request completion logs use static route templates or an `<unmatched>` marker,
  so concrete case identifiers and raw unknown paths never enter the log.
- A losing writer in a review idempotency-key or optimistic-version race has
  its partial writes rolled back before the request is resolved as a safe
  replay or a genuine conflict, so no orphaned duplicate case or event row
  can survive a race.
- No review session token, CSRF token, or actor credential is ever returned
  in a response body, embedded in rendered HTML, or logged.

## [0.1.0] - 2026-08-02

### Added

- Bounded PDF, PNG, and JPEG ingestion with ephemeral temporary storage.
- Replaceable Tesseract OCR with typed page results.
- Typed OpenAI Responses extraction with page-level evidence and uncertainty.
- SQLite-backed reference data behind a repository protocol.
- Deterministic arithmetic, purchase-order, duplicate, historical, and
  line-item verification findings.
- Evidence-grounded explanation with guarded provider proposals and a
  deterministic fallback.
- Complete OCR-to-verdict processing graph, `POST /process`, and stateless local
  `GET /review` interface.
- Safe request correlation, metadata-only logging, synthetic fixtures, and the
  Phase 0 through Phase 6 documentation set.
