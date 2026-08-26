# Veridoc Agent Operating Guide

## Project purpose

Veridoc is an agentic document-intelligence system for deciding whether data
extracted from invoices can be trusted. Its version 1 scope is invoice and
purchase-order reconciliation: extraction is only one stage, and later stages
must compare deterministic facts, reference data, and historical behavior before
returning evidence-backed findings.

Veridoc is not a generic document extraction platform. Do not add KYC,
identity-document, speculative model-training, or generic workflow abstractions.
Keep boundaries reusable where the current invoice use case naturally requires
them, and otherwise follow YAGNI.

## Current phase and implementation

Phase 0 through Phase 9 are complete. Phase 10 and later are not approved. The
runtime implementation remains deliberately small:

- `src/veridoc/__init__.py` exposes package metadata.
- `src/veridoc/__main__.py` starts the local API process.
- `src/veridoc/app.py` creates the FastAPI application, pre-parser body limits,
  validation-first dependencies, safe request correlation, `GET /health`,
  `POST /ocr`, `POST /extract`, `POST /process`, and `GET /review`, and includes
  the authenticated reference-data administration router and the Phase 9
  review router.
- `src/veridoc/ingestion/dependencies.py` and
  `src/veridoc/processing/dependencies.py` own the shared validated-upload and
  OCR/extraction/processing dependency composition, so `app.py` and
  `review/api.py` compose the identical dependency graph rather than each
  maintaining its own.
- `src/veridoc/ingestion/validation.py` bounds and validates PDF, PNG, and JPEG
  uploads before decoding.
- `src/veridoc/ingestion/storage.py` owns ephemeral temporary upload files.
- `src/veridoc/ocr/service.py` decodes raster images, rasterizes PDF pages, and
  can return normalized in-memory page images with OCR output.
- `src/veridoc/ocr/protocol.py` defines the replaceable typed OCR boundary.
- `src/veridoc/ocr/tesseract.py` adapts the selected Tesseract baseline.
- `src/veridoc/extraction/models.py` defines strict typed invoice, line-item,
  evidence, uncertainty, and confidence schemas.
- `src/veridoc/extraction/protocol.py` defines the replaceable async structured
  extraction boundary and safe provider error types.
- `src/veridoc/extraction/graph.py` owns the typed single-node LangGraph flow.
- `src/veridoc/extraction/service.py` composes OCR with the graph.
- `src/veridoc/extraction/openai_responses.py` adapts the configured OpenAI
  Responses API through the typed boundary.
- `src/veridoc/persistence/protocol.py` defines the SQLite-independent invoice
  and purchase-order reference-data repository boundary.
- `src/veridoc/administration/` owns strict administration schemas with
  canonical vendor keys, the repository protocol, local Bearer authentication,
  FastAPI routes, and the maintenance CLI.
- `src/veridoc/persistence/migrations.py` applies numbered forward-only SQLite
  migrations, validates current schemas without a write lock, validates upgrades
  before commit, adds unique parent/position child indexes in migration 4, and
  rejects unsupported future schema versions.
- `src/veridoc/persistence/schema.py` validates the current tables, columns,
  declared types, keys, constraints, foreign keys, required provenance indexes,
  required child-position indexes, and absence of triggers on managed tables.
- `src/veridoc/persistence/sqlite.py` implements processing and administration
  repository boundaries with local SQLite and applies the same canonical,
  bounded record contract to every write and hydrated-row read path.
- `src/veridoc/persistence/maintenance.py` provides non-mutating, integrity-,
  migration-, schema-, and row-semantics-checked online backup plus
  stopped-service atomic restore.
- `src/veridoc/verification/` owns typed findings, deterministic verification
  rules, an API-neutral service, and the typed verification graph.
- `src/veridoc/explanation/` owns strict explanation results and provider drafts,
  deterministic rendering, provider-draft guardrails, an API-neutral service,
  an optional OpenAI adapter, and the typed explanation graph.
- `src/veridoc/processing/` owns the typed final result, deterministic verdict,
  complete OCR-to-verdict graph, and API-neutral processing service.
- `src/veridoc/review/page.py` renders the minimal stateless, unauthenticated
  local `/review` demo page (predates Phase 9 and is unrelated to it).
- `src/veridoc/review/models.py` owns strict, `extra="forbid"` review domain
  schemas, including the digest-verified immutable `ReviewSnapshot` and the
  append-only `ReviewEvent`.
- `src/veridoc/review/transitions.py` owns the deterministic case
  status-transition table and role/assignee authorization rules as pure
  functions.
- `src/veridoc/review/protocol.py` defines the
  `ReviewCaseReader`/`ReviewCaseWriter`/`ReviewSessionStore` boundaries and
  the safe review domain errors.
- `src/veridoc/review/auth.py` and `src/veridoc/review/config.py` own
  credential/session/CSRF handling and actor-file/origin/store
  configuration.
- `src/veridoc/review/persistence/` implements the protocols against a
  dedicated review SQLite store: migrations, schema validation, the
  repository, maintenance (backup/restore), and the `veridoc-review` CLI —
  independent of the reference-data store and its migration ledger.
- `src/veridoc/review/api.py` owns the authenticated FastAPI router: session,
  case, and `/review/console` routes, with auth-before-storage dependency
  ordering.
- `src/veridoc/review/console_page.py` renders the no-build authenticated
  review console.
- `tests/test_app.py` verifies application imports, metadata, and the safe 404
  response.
- `tests/test_health.py` verifies health behavior and its required OpenAPI schema
  without a network server.
- `tests/test_ingestion_*.py`, `tests/test_ocr_*.py`, `tests/test_extraction_*.py`,
  `tests/test_openai_responses.py`, `tests/test_sqlite_repository.py`,
  `tests/test_verification_*.py`, and `tests/test_tesseract.py` cover validation,
  cleanup, OCR contracts, extraction schemas, SQLite persistence, deterministic
  verification, graph composition, mocked provider behavior, and API errors.
- `tests/test_explanation_*.py` and `tests/test_openai_explanations.py` cover
  canonical evidence, numerical context, deterministic fallback, draft
  guardrails, mocked explanation-provider behavior, and graph composition.
- `tests/test_processing_*.py` and `tests/test_review_page.py` cover the final
  result contract, verdict derivation, graph/service composition, dependency
  wiring, endpoint errors, and safe review-page rendering.
- `tests/test_processing_integration.py` covers the complete FastAPI dependency
  graph with a temporary SQLite repository and deterministic external fakes.
- `tests/test_request_context.py` covers safe correlation headers and
  metadata-only request logging.
- `tests/test_request_body_limits.py` and `tests/test_upload_dependency_order.py`
  cover pre-parser body bounds, off-loop validation, deterministic upload
  closure, and validation before external dependencies.
- `tests/test_administration_*.py`, `tests/test_sqlite_migrations.py`, and
  `tests/test_reference_data_maintenance.py` cover canonical vendor keys,
  bounded schemas, fixed-length credential comparison, OpenAPI security,
  auth-before-storage ordering, CRUD, atomic imports, migrations, structural
  backup/restore validation, and CLI failures with temporary databases.
- `scripts/check_distribution.py` validates wheel and source-distribution
  metadata, required contents, regular member types, unique safe paths, and
  sensitive-file exclusions.
- `scripts/smoke_distribution.py` verifies installed metadata, entry points,
  versions, and critical routes for isolated wheel and source-distribution
  installs.
- `tests/test_distribution_check.py` covers archive validation rejection paths.
- `tests/test_documentation.py` validates local Markdown link targets and the
  exact documented test-module inventory as part of the ordinary pytest gate.
- `tests/test_review_models.py`, `tests/test_review_transitions.py`, and
  `tests/test_review_authorization.py` cover the strict domain schemas,
  status transitions, and the complete role/assignee authorization matrix as
  pure functions.
- `tests/test_review_config.py` and `tests/test_review_auth.py` cover
  actor-file/origin configuration and constant-time credential/session/CSRF
  handling.
- `tests/test_review_sqlite_migrations.py`, `tests/test_review_schema.py`,
  `tests/test_review_sqlite_repository.py`,
  `tests/test_review_persistence_concurrency.py`,
  `tests/test_review_data_maintenance.py`, and `tests/test_review_cli.py`
  mirror the reference-data persistence tests independently for the
  dedicated review store, plus a race test proving exactly one writer wins a
  version or idempotency-key conflict.
- `tests/test_review_api.py`, `tests/test_review_session_api.py`, and
  `tests/test_review_case_*_api.py` cover session/CSRF/origin handling and
  every case route's own auth/idempotency/conflict/not-found contract
  through HTTPX's ASGI transport; `tests/test_review_api_error_contracts.py`
  adds the cross-route properties (idempotency conflict, generic
  validation, unavailable-store 503, correlation) no single route test owns.
- `tests/test_review_console_page.py` asserts the console page never uses
  `innerHTML`.
- `tests/test_review_case_creation_integration.py`,
  `tests/test_review_authorization_integration.py`, and
  `tests/test_review_retry_recovery_integration.py` cover the real
  processing graph behind a real login, rejected-actor dependency
  short-circuiting, and retry/concurrency/backup-restore/snapshot-
  independence properties end to end.

Phase 6 completes product behavior, integration coverage, documentation,
fixture guidance, and local operational correlation. Phase 7 adds reproducible
quality and release gates without adding endpoints, domain behavior, deployment
targets, or workflow features. Phase 8 adds controlled local reference-data
operations without adding user accounts, an audit workflow, or deployment
infrastructure. Phase 9 adds a per-actor authenticated, persistent review
workflow — immutable snapshots, append-only events, session/CSRF-protected
routes, and a browser console — in a store fully independent of reference
data, without adding a production identity provider, deployment
infrastructure, or automated retention/purge.

The current and planned workflow is:

```text
ingestion -> OCR -> structured extraction -> verification -> explanation -> verdict
```

The implemented segment ends at the typed processing result and review display.
Later dependencies must point inward: API and graph orchestration may call domain
services and boundary protocols; external OCR, LLM, and persistence adapters
may implement those protocols; domain logic must not import FastAPI, LangGraph,
SQLite connection code, or vendor SDKs.

## Fixed stack

- Use `uv` exclusively for Python versions, dependencies, locking, and commands.
- Use FastAPI for the HTTP API.
- Use LangGraph for the Phase 2 extraction, Phase 3 verification, Phase 4
  explanation, and Phase 5 complete-processing graphs.
- Use the OpenAI Responses API through the typed `StructuredExtractor` protocol
  for Phase 2 vision extraction. Keep the model configurable with
  `VERIDOC_LLM_MODEL`; do not hardcode a model identifier.
- Use the OpenAI Responses API through the typed `FindingExplainer` protocol for
  optional Phase 4 explanation guidance. It receives only canonical verification
  findings, never OCR or document data; application code owns factual and
  numerical context and has a deterministic fallback.
- Tesseract is the selected version 1 OCR baseline and is integrated behind the
  typed `OCREngine` protocol in Phase 1. See ADR 0001 for limitations and
  Arabic/Latin installation and runtime instructions.
- Use SQLite behind the `InvoiceRepository` and
  `ReferenceDataAdminRepository` interfaces. Apply schema changes only through
  the Phase 8 forward-only migration ledger.
- Use SQLite behind the `ReviewCaseReader`/`ReviewCaseWriter`/
  `ReviewSessionStore` interfaces for the Phase 9 review store. It has its
  own forward-only migration ledger, fully independent of the reference-data
  ledger (ADR 0009); never share a table or migration between them without a
  new ADR.
- Use pytest for tests.

Do not replace the fixed stack without asking first. Add dependencies only when
the currently approved phase uses them, and commit `pyproject.toml` and `uv.lock`
together.

## Development commands

Run all commands from the repository root.

```bash
# Create or synchronize the environment from the committed lockfile.
uv sync --all-groups --locked

# Start the API locally.
uv run uvicorn veridoc.app:app --reload

# Run the complete test suite.
uv run pytest

# Run the focused health test.
uv run pytest tests/test_health.py
uv run pytest tests/test_app.py

# Run focused Phase 1 through Phase 9 boundary tests.
uv run pytest tests/test_ingestion_validation.py
uv run pytest tests/test_ingestion_storage.py
uv run pytest tests/test_request_body_limits.py
uv run pytest tests/test_upload_dependency_order.py
uv run pytest tests/test_fixtures.py
uv run pytest tests/test_ocr_models.py
uv run pytest tests/test_ocr_service.py
uv run pytest tests/test_ocr_api.py
uv run pytest tests/test_tesseract.py
uv run pytest tests/test_extraction_models.py
uv run pytest tests/test_extraction_config.py
uv run pytest tests/test_extraction_protocol.py
uv run pytest tests/test_extraction_graph.py
uv run pytest tests/test_extraction_service.py
uv run pytest tests/test_openai_responses.py
uv run pytest tests/test_extraction_api.py
uv run pytest tests/test_sqlite_repository.py
uv run pytest tests/test_verification_models.py
uv run pytest tests/test_verification_references.py
uv run pytest tests/test_verification_arithmetic.py
uv run pytest tests/test_verification_vendors.py
uv run pytest tests/test_verification_repository_checks.py
uv run pytest tests/test_verification_history.py
uv run pytest tests/test_verification_line_items.py
uv run pytest tests/test_verification_field_history.py
uv run pytest tests/test_verification_purchase_orders.py
uv run pytest tests/test_verification_service.py
uv run pytest tests/test_verification_graph.py
uv run pytest tests/test_explanation_models.py
uv run pytest tests/test_explanation_fallback.py
uv run pytest tests/test_explanation_protocol.py
uv run pytest tests/test_explanation_guardrails.py
uv run pytest tests/test_explanation_service.py
uv run pytest tests/test_explanation_config.py
uv run pytest tests/test_openai_explanations.py
uv run pytest tests/test_explanation_graph.py
uv run pytest tests/test_processing_models.py
uv run pytest tests/test_processing_verdict.py
uv run pytest tests/test_processing_graph.py
uv run pytest tests/test_processing_service.py
uv run pytest tests/test_processing_dependencies.py
uv run pytest tests/test_processing_api.py
uv run pytest tests/test_processing_integration.py
uv run pytest tests/test_request_context.py
uv run pytest tests/test_review_page.py
uv run pytest tests/test_distribution_check.py
uv run pytest tests/test_documentation.py
uv run pytest tests/test_administration_models.py
uv run pytest tests/test_administration_auth.py
uv run pytest tests/test_sqlite_migrations.py
uv run pytest tests/test_administration_sqlite_invoices.py
uv run pytest tests/test_administration_sqlite_purchase_orders.py
uv run pytest tests/test_administration_sqlite_import.py
uv run pytest tests/test_administration_invoice_api.py
uv run pytest tests/test_administration_purchase_order_api.py
uv run pytest tests/test_administration_import_api.py
uv run pytest tests/test_reference_data_maintenance.py
uv run pytest tests/test_administration_cli.py
uv run pytest tests/test_review_models.py
uv run pytest tests/test_review_transitions.py
uv run pytest tests/test_review_authorization.py
uv run pytest tests/test_review_protocol.py
uv run pytest tests/test_review_config.py
uv run pytest tests/test_review_auth.py
uv run pytest tests/test_review_schema.py
uv run pytest tests/test_review_sqlite_migrations.py
uv run pytest tests/test_review_sqlite_repository.py
uv run pytest tests/test_review_persistence_concurrency.py
uv run pytest tests/test_review_data_maintenance.py
uv run pytest tests/test_review_cli.py
uv run pytest tests/test_review_api.py
uv run pytest tests/test_review_session_api.py
uv run pytest tests/test_review_case_creation_api.py
uv run pytest tests/test_review_case_listing_api.py
uv run pytest tests/test_review_case_detail_api.py
uv run pytest tests/test_review_case_assignment_api.py
uv run pytest tests/test_review_case_escalation_api.py
uv run pytest tests/test_review_case_decision_api.py
uv run pytest tests/test_review_api_error_contracts.py
uv run pytest tests/test_review_console_page.py
uv run pytest tests/test_review_case_creation_integration.py
uv run pytest tests/test_review_authorization_integration.py
uv run pytest tests/test_review_retry_recovery_integration.py

# Inspect the reference-data maintenance interface.
uv run veridoc-reference --help

# Inspect the review-store maintenance interface.
uv run veridoc-review --help

# Check lint and formatting.
uv run ruff check .
uv run ruff format --check .

# Check production type contracts.
uv run mypy

# Run the full branch-coverage gate.
uv run pytest --cov=veridoc

# Confirm pyproject.toml and uv.lock agree.
uv lock --check

# Audit the synchronized third-party environment.
uv run pip-audit

# Build and validate distribution metadata.
uv build --clear
uv run twine check dist/*
uv run python scripts/check_distribution.py

# Apply formatting when needed.
uv run ruff format .
```

Mypy strictly checks `src/veridoc`. Runtime-negative tests deliberately exercise
Pydantic coercion and rejection paths, so pytest remains their validation gate.

Add runtime dependencies with `uv add <package>` and development dependencies
with `uv add --dev <package>`. Never use pip, Conda, Poetry, Pipenv, or a
`requirements.txt` file as the primary dependency workflow.

## Atomic commit protocol

Every commit must be the smallest meaningful, independently reviewable change
that leaves the repository coherent.

1. Select one tiny logical change and state its intended commit purpose.
2. Edit only the files needed for that purpose.
3. Run the most focused relevant test and every configured lint, format, type,
   import, lock, or documentation check that applies.
4. Run `git status --short` and `git diff`.
5. Stage only named files; never use `git add .` or `git add -A`.
6. Run `git diff --staged` and confirm it contains exactly one concern.
7. Commit immediately with a specific Conventional Commit message.
8. Run `git status --short`; it must be empty before the next change.

Keep one concern per commit. Split dependency additions, behaviors, substantial
test groups, refactors, and independent documentation topics. A behavior and a
small inseparable test may share a commit when separating them would leave a
broken or misleading state. Never accumulate completed changes for a later bulk
commit.

Do not squash, amend, reorder, rebase, or otherwise rewrite commits unless the
user explicitly requests it. Do not create WIP, empty, placeholder, or knowingly
failing commits. Do not make unrelated "while here" edits. Preserve user changes
and stop if they overlap the current change in a way that cannot be isolated.

Use these commit prefixes: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, and
`refactor:`. Add a body when the reason or tradeoff is not obvious.

After each commit, report its short hash and message, purpose, changed files,
validation evidence, and clean-tree status. Before starting the next change,
state its exact intended purpose.

## Testing expectations

- Add focused tests with every behavior change unless the commit has no testable
  behavior.
- Keep unit tests close to deterministic domain behavior and node-level tests
  focused on one graph stage.
- Test error paths at every I/O boundary when that boundary is introduced.
- Add a small number of high-value graph integration scenarios rather than a
  broad shallow end-to-end suite.
- Mock the OCR engine protocol, `StructuredExtractor`, `FindingExplainer`, OpenAI
  client, remote storage, and other external services. Tests must not require
  credentials, network access, or an installed Tesseract executable. Complete
  processing tests must retain the real typed graph and deterministic services;
  at least one Phase 6 ASGI scenario must retain real dependency composition and
  temporary SQLite reference data.
- Administration API tests must inject the repository protocol and synthetic
  credentials. Migration, CRUD, import, backup, restore, and CLI tests must use
  temporary SQLite paths and must not touch a configured developer database.
- Test authentication failures before storage resolution, bounded import
  rejection before parsing/writing, transactional conflict behavior, migration
  compatibility, incomplete maintenance schemas, and restore integrity/atomicity
  at those boundaries.
- Review tests must inject a fictional `ReviewActorDirectory` and a temporary
  or in-memory `SQLiteReviewRepository`, never a real operator actor file.
  Prove a rejected actor, missing/invalid session, or CSRF/origin failure
  never resolves the processing pipeline or a review-store write; prove
  every mutation's `expected_version` and `Idempotency-Key` guards; and
  prove the console page renders every fetched value through
  `textContent`/`createTextNode`, never `innerHTML`.
- Use only deterministic synthetic or appropriately licensed fixtures. Never
  copy real invoice or customer data into tests.
- Run the full suite after dependency, cross-cutting, or graph integration
  changes and before completing a phase.

For documentation-only changes, run `uv run pytest tests/test_documentation.py`,
verify every referenced command, and run the focused health test when the
documented development workflow is affected.

## Documentation expectations

`README.md` is the concise user and contributor entry point. The current
documentation set is:

- `CHANGELOG.md` for completed version scope and unreleased changes;
- `docs/architecture.md` for current boundaries and the explicitly planned flow;
- `docs/development.md` for setup, commands, configuration, and workflow;
- `docs/testing.md` for tests, fixtures, mocks, and required evidence;
- `docs/data-and-security.md` for data, secret, logging, upload, and retention
  rules;
- `docs/api.md` for implemented endpoints and limitations;
- `docs/roadmap.md` for approved work and later unapproved phase candidates;
- `docs/phase-9-plan.md` for the approved Phase 9 design, exact atomic commit
  sequence, verification checkpoints, and approval boundary — every item in
  its sequence is implemented;
- `docs/release-evidence.md` for local phase-gate results and evidence
  boundaries;
- `docs/decisions/README.md` for ADR conventions and the decision index.
- `docs/decisions/0001-use-tesseract-for-v1.md` for the OCR baseline decision.
- `docs/decisions/0002-use-openai-responses-for-phase-2.md` for the extraction
  provider decision.
- `docs/decisions/0003-use-sqlite-for-phase-3-reference-data.md` for the local
  reference-data persistence decision.
- `docs/decisions/0004-use-validated-llm-proposals-for-explanations.md` for the
  explanation-provider safety decision.
- `docs/decisions/0005-use-review-required-processing-verdicts.md` for the
  deterministic processing-verdict decision.
- `docs/decisions/0006-use-bearer-token-for-local-administration.md` for the
  local administration authentication decision.
- `docs/decisions/0007-use-forward-only-sqlite-migrations.md` for the schema
  evolution decision.
- `docs/decisions/0008-use-local-actor-file-and-http-only-sessions-for-review.md`
  for the review actor/session/CSRF design decision.
- `docs/decisions/0009-use-immutable-versioned-review-records.md` for the
  immutable versioned review-record decision.
- `docs/decisions/0010-defer-automated-review-retention-and-purge.md` for the
  deferred review retention/purge decision.
- `tests/fixtures/README.md` for deterministic fictional fixture use and
  extension guidance.

Do not claim that planned endpoints or later-phase capabilities already exist.

Update documentation with the related feature or in the immediately following
focused documentation commit. Link between documents instead of copying large
sections. Use `docs/decisions/` for meaningful architecture decisions with
title, status, context, decision, alternatives, and consequences; do not create
ADRs for trivial choices.

Update this guide when commands, package boundaries, test conventions, required
checks, phase status, or architectural decisions change. A workflow change must
update this file in the same commit when inseparable or in the immediately
following documentation commit.

## Security and data rules

- Never commit real invoices, production documents, personal information,
  customer data, credentials, or confidential business data.
- Commit only synthetic, fictional, programmatically generated, or appropriately
  licensed public fixtures.
- Never commit `.env`; keep only safe placeholders in `.env.example`.
- Read configuration from the environment and validate required values before
  the configured external boundary is invoked.
- Do not log document bodies, secrets, credentials, or sensitive extracted
  fields. Use correlation identifiers and stage names for operational context.
- Validate total request and file sizes, content type, signature, per-page and
  cumulative pixel bounds, and filenames before expensive parsing or external
  dependency construction at the implemented upload boundary. Enforce the
  normalized-image bundle size while encoding, before retaining an oversized
  result.
- Treat extracted provider values as untrusted: bound decimals before arithmetic,
  require evidence pages to exist, and ground supplied OCR spans in normalized
  page text before verification.
- Bound extraction and explanation provider calls to the fixed 120-second
  application deadline and close request-scoped provider clients at dependency
  teardown.
- Bound streaming reads, isolate temporary files, clean them up deterministically,
  and document ephemeral retention behavior.
- Public errors must not expose internal paths, stack traces, secrets, or raw
  document content.
- Require `VERIDOC_ADMIN_TOKEN` only at the administration boundary, hash both
  credential values to fixed-length SHA-256 digests before constant-time
  comparison, never accept it in URLs or bodies, and resolve storage only after
  authentication succeeds.
- Bound administration create/update JSON bodies and import files to 1 MiB
  before parsing; imports allow 500 total records and 200 line items per record.
  Preserve immutable provenance and apply bulk writes in one transaction.
- Treat local SQLite files and backups as sensitive reference data. Restore only
  while the service is stopped, reject live WAL/SHM/rollback-journal sidecars,
  keep online backup sources and published snapshots at their original schema
  version, and replace a database or backup only after database and foreign-key
  integrity, migration-history, required-schema, and persisted-row semantic
  checks pass.
- Require `VERIDOC_REVIEW_ACTORS_FILE` and `VERIDOC_REVIEW_ORIGIN` (an exact
  HTTPS origin) at the review boundary; compare presented credentials to
  stored digests with a constant-time scan over every actor, never
  short-circuiting on the first match. Never accept a review credential in a
  URL or query value, and never return a raw credential or session token in
  a response body.
- Require session, CSRF (`X-CSRF-Token` matching a non-`HttpOnly` cookie),
  and exact-origin checks before resolving any review repository or
  processing dependency, including the untrusted document upload path.
- Treat the review database as sensitive review data, fully independent of
  the reference database and its migration ledger. Every review case's
  snapshot is immutable and digest-verified; every mutation appends one
  event under an `expected_version` guard and an `Idempotency-Key` — never
  edit a case or event in place.
- Render every value a review route returns with DOM text nodes only
  (`textContent`/`createTextNode`); never use `innerHTML` in the review
  console, since extracted document content is untrusted.

## Phase boundaries

- Phase 0: repository hygiene, `uv` scaffold, FastAPI application, typed health
  endpoint, focused tests, and accurate initial documentation. **Complete.**
- Phase 1: safe ingestion and one documented OCR baseline. **Complete.**
- Phase 2: typed invoice extraction and LangGraph state/node. **Complete.**
- Phase 3: SQLite repository and deterministic/statistical verification.
  **Complete.**
- Phase 4: evidence-grounded explanation with deterministic fallback.
  **Complete.**
- Phase 5: complete processing API and minimal review interface. **Complete.**
- Phase 6: final integration, documentation, and operational pass. **Complete.**
- Phase 7: release engineering and reproducible quality gates. **Complete.**
- Phase 8: controlled local reference-data administration, migrations, bounded
  imports, and backup/restore. **Complete.**
- Phase 9: per-actor authenticated, persistent review/audit workflow —
  immutable snapshots, append-only events, session/CSRF-protected routes,
  and a browser console, in a store independent of reference data.
  **Complete.**
- Phase 10 through Phase 11: candidate deployment security and readiness
  evaluation. **Planned; not approved.** See `docs/roadmap.md` for their
  boundaries.

Do not begin Phase 10. Before Phase 10 or any later phase, inspect the
repository, run the existing suite, present the implementation and commit
plan, identify documentation changes, and wait for explicit approval. Phase
9's approval identified `docs/phase-9-plan.md` and did not extend to Phase 10
or Phase 11; the same rule applies to any future phase's approval.
