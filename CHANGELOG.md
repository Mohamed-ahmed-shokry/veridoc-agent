# Changelog

All notable project changes are recorded here. The project follows
[Keep a Changelog](https://keepachangelog.com/en/1.1.0/) categories and will use
semantic versions for tagged releases.

## [Unreleased]

### Added

- Phase 7 roadmap and explicit approval boundaries for later candidate phases.
- Strict mypy checks for the production package.
- A 90% branch-aware coverage floor, established from a 93.35% baseline.
- GitHub Actions checks for locked sync, audit, lint, format, types, coverage,
  builds, package validation, and isolated-wheel imports.
- Locked dependency-vulnerability and distribution-metadata tooling.
- Safe wheel and source-distribution content validation.
- Bearer-authenticated invoice and purchase-order reference-data administration.
- Strict provenance/retention schemas and bounded paginated CRUD endpoints.
- Atomic JSON imports with reject, skip, replace, and dry-run conflict policies.
- Numbered forward-only SQLite migrations with legacy metadata backfill.
- Online SQLite backup and stopped-service validated atomic restore commands.
- A `veridoc-reference` maintenance entry point and Phase 8 focused tests.

### Changed

- Typed graph builders, provider inputs, numeric calculations, decoder values,
  SQLite insert identifiers, and request middleware now satisfy the strict gate.
- Package metadata now uses `README.md` as its Markdown long description.
- Reference persistence initializes through the migration ledger and closes all
  SQLite connections explicitly.
- Fictional PDF fixtures suppress generated trailer IDs for reproducible bytes.
- Distribution validation now requires Phase 8 modules and both console scripts.

### Security

- Administration validates a 32-256 character local token and compares Bearer
  credentials in constant time before resolving the reference database.
- Raw imports are limited to 1 MiB, 500 records, and 200 line items per record.
- Restore refuses live WAL/SHM sidecars and replaces the database only after
  integrity and migration checks succeed.

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
