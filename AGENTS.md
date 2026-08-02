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

Phase 0, Phase 1, Phase 2, Phase 3, Phase 4, Phase 5, and Phase 6 are complete.
Phase 7 release engineering is also complete. No later phase is approved. The
runtime implementation is deliberately small:

- `src/veridoc/__init__.py` exposes package metadata.
- `src/veridoc/__main__.py` starts the local API process.
- `src/veridoc/app.py` creates the FastAPI application, safe request correlation,
  `GET /health`, `POST /ocr`, `POST /extract`, `POST /process`, and `GET
  /review`.
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
- `src/veridoc/persistence/sqlite.py` implements that boundary with local SQLite.
- `src/veridoc/verification/` owns typed findings, deterministic verification
  rules, an API-neutral service, and the typed verification graph.
- `src/veridoc/explanation/` owns strict explanation results and provider drafts,
  deterministic rendering, provider-draft guardrails, an API-neutral service,
  an optional OpenAI adapter, and the typed explanation graph.
- `src/veridoc/processing/` owns the typed final result, deterministic verdict,
  complete OCR-to-verdict graph, and API-neutral processing service.
- `src/veridoc/review/` renders the minimal stateless local review page.
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
- `scripts/check_distribution.py` validates wheel and source-distribution
  metadata, required contents, safe paths, and sensitive-file exclusions.
- `tests/test_distribution_check.py` covers archive validation rejection paths.

Phase 6 completes product behavior, integration coverage, documentation,
fixture guidance, and local operational correlation. Phase 7 adds reproducible
quality and release gates without adding endpoints, domain behavior, deployment
targets, or workflow features.

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
- Use SQLite behind the `InvoiceRepository` interface for Phase 3 reference data
  and Phase 5 processing lookups.
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

# Run focused Phase 1 through Phase 6 boundary tests.
uv run pytest tests/test_ingestion_validation.py
uv run pytest tests/test_ocr_service.py
uv run pytest tests/test_ocr_api.py
uv run pytest tests/test_extraction_models.py
uv run pytest tests/test_extraction_graph.py
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
- Use only deterministic synthetic or appropriately licensed fixtures. Never
  copy real invoice or customer data into tests.
- Run the full suite after dependency, cross-cutting, or graph integration
  changes and before completing a phase.

For documentation-only changes, verify every referenced path and command and run
the focused health test when the documented development workflow is affected.

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
- Validate content type, signature, size, page/pixel bounds, and filenames before
  expensive parsing at the implemented upload boundary.
- Bound streaming reads, isolate temporary files, clean them up deterministically,
  and document ephemeral retention behavior.
- Public errors must not expose internal paths, stack traces, secrets, or raw
  document content.

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
- Phase 8 through Phase 11: candidate reference-data administration, review and
  audit persistence, deployment security, and readiness evaluation. **Planned;
  not approved.** See `docs/roadmap.md` for their boundaries.

Version 1 product behavior is complete through Phase 6, and Phase 7 release
engineering is complete. Before Phase 8 or any later phase, inspect the
repository, run the existing suite, present the implementation and commit plan,
identify documentation changes, and wait for explicit approval.
