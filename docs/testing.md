# Testing

Veridoc uses pytest. The Phase 8 suite covers the FastAPI application, bounded
upload validation outside the async request loop, temporary-file cleanup, typed
OCR contracts, normalized page images, structured invoice schemas, typed
extraction and verification graphs, the mocked OpenAI adapter, local SQLite
reference persistence, and deterministic invoice verification rules. It also
covers strict explanation schemas,
deterministic explanation rendering, provider-draft guardrails, mocked
explanation providers, the typed explanation graph, the complete processing
graph/service/API, safe reference-data failures, and the local review page.
Phase 7 additionally enforces strict static typing for the production package.
Phase 8 adds bounded administration schemas, local Bearer authentication,
forward-only migrations, invoice and purchase-order CRUD, atomic conflict-aware
imports, and backup/restore maintenance tests.

## Test organization

Tests live under `tests/`:

```text
tests/
├── fixtures/README.md             fixture generation and extension guidance
├── fixtures/fictional_invoice.py  deterministic synthetic PDF/PNG generators
├── test_app.py                    application import and metadata
├── test_health.py                 health behavior and OpenAPI contract
├── test_ingestion_validation.py   signatures, limits, mismatch, streaming
├── test_ingestion_storage.py      temporary-file cleanup
├── test_request_body_limits.py    pre-parser request-body byte limits
├── test_upload_dependency_order.py  validation-before-dependency ordering
├── test_ocr_models.py             typed result and response contracts
├── test_tesseract.py              mocked adapter parsing and failures
├── test_ocr_service.py            raster/PDF page orchestration
├── test_ocr_api.py                in-process multipart endpoint behavior
├── test_extraction_models.py       typed invoice and evidence contract
├── test_extraction_protocol.py     OCR/page request boundary invariant
├── test_extraction_graph.py        typed LangGraph extraction node
├── test_extraction_config.py       provider configuration validation
├── test_openai_responses.py        mocked Responses input and failure mapping
├── test_extraction_service.py      OCR-to-graph composition
├── test_extraction_api.py          in-process extraction endpoint behavior
├── test_sqlite_repository.py       SQLite invoice/PO round trips and lookups
├── test_sqlite_migrations.py       ordered migration and compatibility checks
├── test_administration_models.py   bounded admin and import schemas
├── test_administration_auth.py     token configuration and authentication
├── test_administration_sqlite_invoices.py  invoice administration persistence
├── test_administration_sqlite_purchase_orders.py  PO administration persistence
├── test_administration_sqlite_import.py  atomic conflict-policy imports
├── test_administration_invoice_api.py  authenticated invoice API behavior
├── test_administration_purchase_order_api.py  authenticated PO API behavior
├── test_administration_import_api.py  bounded JSON import API behavior
├── test_reference_data_maintenance.py  safe SQLite backup and restore
├── test_administration_cli.py      maintenance CLI contracts
├── test_verification_models.py     typed finding evidence contract
├── test_verification_references.py reference invoice and PO facts
├── test_verification_arithmetic.py deterministic arithmetic and date rules
├── test_verification_history.py    total statistics and insufficient history
├── test_verification_line_items.py occurrence, price, and quantity comparison
├── test_verification_field_history.py  payment-term consistency checks
├── test_verification_purchase_orders.py  PO header and line reconciliation
├── test_verification_service.py    API-neutral check composition
├── test_verification_graph.py      typed LangGraph verification node
├── test_explanation_models.py      typed explanation result contract
├── test_explanation_fallback.py    deterministic evidence/numerical rendering
├── test_explanation_protocol.py    provider request and draft contracts
├── test_explanation_guardrails.py  unsafe provider-draft rejection
├── test_explanation_service.py     fallback and provider composition
├── test_explanation_config.py      provider configuration validation
├── test_openai_explanations.py     mocked provider input and failures
├── test_explanation_graph.py       typed LangGraph explanation node
├── test_processing_models.py        strict final result and verdict contract
├── test_processing_verdict.py       deterministic verdict derivation
├── test_processing_graph.py         complete typed OCR-to-verdict graph
├── test_processing_service.py       full typed service scenarios
├── test_processing_dependencies.py  local database and fallback composition
├── test_processing_api.py           in-process complete processing endpoint
├── test_processing_integration.py   complete FastAPI dependency composition
├── test_request_context.py          safe correlation header and request logs
├── test_review_page.py              local review-interface route
├── test_distribution_check.py       release archive safety checks
└── test_fixtures.py               fixture determinism
```

Name test modules `test_<subject>.py` and test functions
`test_<expected_behavior>`. Use docstrings when the reason for an assertion is
not obvious from its name.

## Run tests

Install all dependency groups first:

```bash
uv sync --all-groups --locked
```

Run the complete suite:

```bash
uv run pytest
```

Run representative focused Phase 1 through Phase 8 modules:

```bash
uv run pytest tests/test_ingestion_validation.py
uv run pytest tests/test_request_body_limits.py
uv run pytest tests/test_upload_dependency_order.py
uv run pytest tests/test_ocr_service.py
uv run pytest tests/test_ocr_api.py
uv run pytest tests/test_extraction_models.py
uv run pytest tests/test_extraction_graph.py
uv run pytest tests/test_openai_responses.py
uv run pytest tests/test_extraction_api.py
uv run pytest tests/test_sqlite_repository.py
uv run pytest tests/test_verification_arithmetic.py
uv run pytest tests/test_verification_history.py
uv run pytest tests/test_verification_line_items.py
uv run pytest tests/test_verification_purchase_orders.py
uv run pytest tests/test_verification_service.py
uv run pytest tests/test_verification_graph.py
uv run pytest tests/test_explanation_fallback.py
uv run pytest tests/test_explanation_guardrails.py
uv run pytest tests/test_explanation_service.py
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
```

Run one behavior by node ID:

```bash
uv run pytest tests/test_ocr_api.py::test_ocr_endpoint_returns_raw_text_and_confidence
```

Use `-q` locally when compact output is useful. Do not hide failures or
warnings in committed automation.

## Unit and integration boundaries

`test_ingestion_validation.py` tests cheap signature, declared-type, filename,
streaming, page, and per-page/cumulative decoded-pixel controls without an HTTP
server. `test_request_body_limits.py` proves declared and streamed request bodies
are rejected before multipart or JSON routing, including under an ASGI root
path. `test_upload_dependency_order.py` proves invalid documents do not construct
OCR, provider, processing, or storage dependencies.

`test_ingestion_storage.py` proves temporary files and directories disappear
after the context exits.

`test_ocr_models.py` tests typed internal and public response values.

`test_tesseract.py` mocks pytesseract's data call so line reconstruction,
bounded finite confidence aggregation, command restoration, and
unavailable-engine mapping are deterministic and do not require a local
Tesseract executable.

`test_ocr_service.py` uses synthetic Pillow and PyMuPDF pages with a fake engine
to test sequential image/PDF decoding, page composition, the aggregate PNG
bundle bound, and normalized page inputs for vision extraction.

`test_ocr_api.py` calls the FastAPI app through HTTPX's ASGI transport and
overrides the engine dependency. It verifies successful raw text, safe type
mismatch errors, and unavailable-engine responses without binding a port.

`test_extraction_models.py` validates nullable invoice fields, dates, bounded
decimals, confidence bounds, evidence references, and schema strictness.

`test_extraction_protocol.py` validates that OCR pages and image pages align.
`test_extraction_graph.py` exercises the single typed LangGraph node with a fake
extractor, including page-range and normalized OCR-span grounding.
`test_extraction_service.py` proves the service passes both OCR text and
normalized page images into that graph.

`test_openai_responses.py` uses a fake SDK client to verify structured parsing,
OCR-text/image construction, deterministic OCR confidence, unavailable-provider
mapping, and invalid-output mapping without credentials or network access.

`test_extraction_api.py` calls `/extract` through HTTPX's ASGI transport with
fake OCR and extraction dependencies. It covers the typed evidence-linked
response and safe 503/422 extraction errors without binding a port.

`test_sqlite_repository.py` uses a temporary SQLite file and fictional reference
facts to prove schema initialization, decimal/date line-item round trips, and
vendor-scoped lookups. It never reads a developer's local database.

`test_verification_*.py` uses strict models, synthetic vendor history, and fake
repositories to exercise arithmetic, duplicate, PO, historical, and
insufficient-history outcomes without a network service, an LLM, or an API
endpoint. `test_verification_graph.py` verifies the single typed graph stage.

`test_explanation_models.py` and `test_explanation_protocol.py` enforce strict
canonical result and provider-draft shapes. `test_explanation_fallback.py`
proves numerical context comes only from the verification finding.
`test_explanation_guardrails.py` rejects incomplete, numeric, and contradictory
provider prose. `test_explanation_service.py` proves invalid or unavailable
provider work falls back to deterministic explanations, while
`test_explanation_graph.py` exercises the single typed graph stage.

`test_openai_explanations.py` uses a fake SDK client to prove the adapter sends
only canonical findings, disables response storage, maps availability failures
safely, and rejects missing structured output.

`test_processing_models.py` and `test_processing_verdict.py` enforce the strict
final result shape and its deterministic `clear`/`review_required` semantics.
`test_processing_graph.py` exercises every typed stage from a validated upload
to a final result. `test_processing_service.py` includes both a no-finding
scenario and a duplicate-invoice scenario that carries canonical findings into
deterministic explanation and review-required verdict output.

`test_processing_dependencies.py` proves the configured temporary reference
database initializes and the explanation layer falls back without provider
settings. `test_processing_api.py` calls `/process` through HTTPX's ASGI
transport with a fake processing service, covering typed payload delivery,
missing extraction configuration, and safe orchestration/reference-data errors.
`test_processing_integration.py` retains the actual FastAPI dependency graph,
temporary SQLite repository, processing graph, verification, and deterministic
explanation service while replacing only OCR and extraction external boundaries.
It proves that a duplicate reference invoice reaches the typed response without
persisting the current upload. `test_request_context.py` covers safe correlation
headers, generic correlated server errors, and request logs that omit query
values.
`test_review_page.py` verifies that the local review form targets `/process` and
renders response values through text nodes rather than injected HTML.

`test_administration_models.py` exercises canonical vendor keys plus strict
provenance, retention, and batch-size bounds before persistence.
`test_administration_auth.py` covers configuration errors, fixed-length digest
comparison behavior, generic authentication failures, and the Bearer challenge
without recording a real secret.

`test_sqlite_migrations.py` builds temporary legacy and current databases to
prove migrations run once, in order, and reject unsupported future versions.
The administration persistence tests use temporary SQLite files to cover CRUD,
immutable provenance, purchase-order natural-key conflicts, and transactional
`reject`, `skip`, and `replace` imports. API tests retain FastAPI dependency
composition while replacing the repository protocol and prove list filters use
the same vendor-key normalization as records; they require neither a network
listener nor a developer database.

`test_sqlite_migrations.py` also races concurrent initialization against one
fresh temporary database. `test_reference_data_maintenance.py` uses temporary
databases to prove database and foreign-key integrity, key/constraint/index
validation, stopped-service restore validation, atomic replacement, destination
preservation, and active WAL/SHM/rollback-journal refusal.
`test_administration_cli.py` exercises help, confirmation, and safe failure
behavior without touching configured developer data.

## Fixtures

Fixtures are generated by `tests/fixtures/fictional_invoice.py` from
fixed inputs. They contain fictional vendor, invoice, purchase-order, and total
text only, and their output is asserted deterministic.

Use [the fixture guide](../tests/fixtures/README.md) for the supported PNG/PDF
generators and the required process for adding a scenario.

Future invoice fixtures must be synthetic, fictional, programmatically
generated, or drawn from an appropriately licensed public subset. They must
contain no real customer data, personal information, credentials, or production
documents.

Fixtures should be:

- deterministic across machines and runs;
- minimal for the behavior being tested;
- explicit about expected fields or OCR text;
- independent of wall-clock time unless time is injected; and
- small enough to review in the same commit as their scenario.

Do not invent large fixture collections before a focused test requires them.

## External-service and executable mocking

No network service or LLM is called in tests. Tesseract is an external local
executable, so adapter tests mock pytesseract and service/API tests inject a
fake `OCREngine`. Extraction and explanation Responses adapter tests use fake
clients, while graph, service, and API tests inject a fake
`StructuredExtractor` or `FindingExplainer`. Verification tests use the
`InvoiceRepository` boundary or a temporary SQLite file. Tests must not require
API keys, network access, an installed OCR executable, or machine-specific
configuration.

Complete-processing tests use fake OCR/extraction boundaries and a synthetic
repository. They exercise real typed graph composition, deterministic
verification, explanation fallback, and verdict derivation without calling a
provider or Tesseract.

Administration API tests inject a fake `ReferenceDataAdminRepository` and a
synthetic token. Persistence, migration, import, backup, and restore tests use
only pytest temporary directories. They never require credentials, a running
service, or an existing local SQLite file.

Mock at the typed boundary protocol rather than patching deep vendor internals.
Keep deterministic decoding, validation, and Pydantic schema validation real;
replace only external OCR or model execution.

## Quality checks

Run lint and formatting checks with the tests:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy
uv run pytest --cov=veridoc
```

Mypy strictly checks `src/veridoc`; pytest remains responsible for tests that
deliberately exercise Pydantic coercion and invalid runtime input. The full
coverage command measures statements and branches and fails below 90%; the
baseline that established the Phase 7 floor was 93.35%. Focused test commands
do not collect coverage, so they remain suitable for atomic changes.

## Required evidence by change type

| Change | Minimum focused evidence |
| --- | --- |
| Documentation only | Verify paths, commands, examples, and links |
| Validation or decoder module | Focused success/error pytest, Ruff lint, Ruff format check |
| OCR adapter or service | Mocked boundary tests, Ruff lint, Ruff format check |
| Extraction schema, graph, or adapter | Typed-boundary tests, mocked provider tests, Ruff lint, Ruff format check |
| Persistence adapter | Temporary SQLite integration tests, Ruff lint, Ruff format check |
| SQLite migration | Legacy/current/future schema tests, repository regression tests, Ruff lint, Ruff format check |
| Administration schema or authentication | Bound/error tests, credential-response tests, Ruff lint, Ruff format check |
| Administration repository CRUD or import | Temporary SQLite success/conflict/rollback tests, Ruff lint, Ruff format check |
| Administration API | Authenticated ASGI success plus 401/409/413/422/503 paths that apply |
| Reference-data backup, restore, or CLI | Temporary SQLite integrity/atomicity tests and CLI safe-failure tests |
| Verification rule, service, or graph | Normal/anomalous synthetic tests, Ruff lint, Ruff format check |
| Explanation schema, service, or graph | Canonical-evidence and fallback tests, Ruff lint, Ruff format check |
| Explanation provider adapter | Mocked request, unavailable, and invalid-output tests |
| Complete processing graph or service | Full typed success scenario and relevant safe error test |
| Processing API or review interface | ASGI contract test; inspect the review route's submission/rendering contract |
| Complete processing integration | ASGI test with real dependency composition and temporary reference data |
| Request correlation or operational logging | Header and metadata-only log test |
| API behavior or schema | Success and relevant error/contract tests |
| Dependency or lockfile | `uv lock --check`, full pytest, applicable quality checks |
| Dependency audit | `uv run pip-audit`; document any explicit advisory exception |
| Distribution packaging | Fresh build, Twine check, archive-content check, isolated-wheel import |
| Production type contract | Focused pytest, `uv run mypy`, Ruff lint, Ruff format check |
| Phase completion | Clean sync, isolated import, coverage gate, mypy, lint, format, runtime smoke test, clean Git status |

Run the full suite before completing a phase even when every individual commit
already had a focused check. See `AGENTS.md` for staging and commit rules and
`docs/development.md` for the development workflow.
