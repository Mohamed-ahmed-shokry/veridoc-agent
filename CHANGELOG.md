# Changelog

All notable project changes are recorded here. The project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) categories and will use
semantic versions for tagged releases.

## [Unreleased]

### Added

- Detailed, approval-gated implementation plans for candidate Phases 9 through
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
  explanation expiry uses deterministic fallback guidance.
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
- Online backup preserves the live source and the published snapshot at their
  original schema version while validating a disposable migrated copy.
- Backup and restore validation copies commit migrations only after the final
  structural schema validator succeeds in the same transaction.
- Ruff targets Python 3.12 explicitly; pytest rejects unknown configuration and
  markers; CI scans tracked whitespace and verifies critical installed routes,
  entry points, and version parity.
- CI pins the checkout action by full release SHA, disables persisted checkout
  credentials, and pins the validated uv CLI version.

### Security

- Administration validates a 32-256 character local token and compares
  fixed-length credential digests in constant time before resolving the
  reference database.
- Administration create/update JSON bodies and raw imports are limited to 1 MiB
  before parsing; imports allow 500 records and 200 line items per record.
- Backup and restore reject incomplete current schemas and replace destinations
  only after structural and persisted-row semantic checks succeed.
- Document/import multipart bodies are bounded before parsing, including under
  ASGI mounts or root paths; PDFs have a cumulative raster-pixel limit;
  normalized vision inputs enforce an aggregate byte limit during PNG encoding;
  Tesseract execution is time-bounded; and invalid OCR confidence values are
  excluded from aggregates.
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
  sidecars.
- Backup and restore open validated source databases in no-create mode, so a
  source removed concurrently cannot be recreated empty or replace good data.

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
