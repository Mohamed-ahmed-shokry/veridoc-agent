# Changelog

All notable project changes are recorded here. The project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) categories and will use
semantic versions for tagged releases.

## [Unreleased]

### Added

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
  review storage resolves; the console clears the credential field after every
  login attempt.
- Review configuration rejects non-origin URL variants and database hard-link
  aliases, while schema and maintenance validation now verify exact columns,
  query indexes, event transitions, current assignees, idempotency rows, and
  session rows.
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
