# Testing

Veridoc uses pytest. The Phase 3 suite covers the FastAPI application, bounded
upload validation, temporary-file cleanup, typed OCR contracts, normalized page
images, structured invoice schemas, typed extraction and verification graphs,
the mocked OpenAI adapter, local SQLite reference persistence, and deterministic
invoice verification rules.

## Test organization

Tests live under `tests/`:

```text
tests/
├── fixtures/fictional_invoice.py  deterministic synthetic PDF/PNG generators
├── test_app.py                    application import and metadata
├── test_health.py                 health behavior and OpenAPI contract
├── test_ingestion_validation.py   signatures, limits, mismatch, streaming
├── test_ingestion_storage.py      temporary-file cleanup
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
├── test_verification_models.py     typed finding evidence contract
├── test_verification_references.py reference invoice and PO facts
├── test_verification_arithmetic.py deterministic arithmetic and date rules
├── test_verification_history.py    total statistics and insufficient history
├── test_verification_line_items.py occurrence, price, and quantity comparison
├── test_verification_field_history.py  payment-term consistency checks
├── test_verification_purchase_orders.py  PO header and line reconciliation
├── test_verification_service.py    API-neutral check composition
├── test_verification_graph.py      typed LangGraph verification node
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

Run focused Phase 2 and Phase 3 modules:

```bash
uv run pytest tests/test_ingestion_validation.py
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
```

Run one behavior by node ID:

```bash
uv run pytest tests/test_ocr_api.py::test_ocr_endpoint_returns_raw_text_and_confidence
```

Use `-q` locally when compact output is useful. Do not hide failures or
warnings in committed automation.

## Unit and integration boundaries

`test_ingestion_validation.py` tests cheap signature, declared-type, filename,
streaming, page, and decoded-pixel controls without an HTTP server.

`test_ingestion_storage.py` proves temporary files and directories disappear
after the context exits.

`test_ocr_models.py` tests typed internal and public response values.

`test_tesseract.py` mocks pytesseract's data call so line reconstruction,
confidence aggregation, command restoration, and unavailable-engine mapping are
deterministic and do not require a local Tesseract executable.

`test_ocr_service.py` uses synthetic Pillow and PyMuPDF pages with a fake engine
to test sequential image/PDF decoding, page composition, and normalized PNG
page inputs for vision extraction.

`test_ocr_api.py` calls the FastAPI app through HTTPX's ASGI transport and
overrides the engine dependency. It verifies successful raw text, safe type
mismatch errors, and unavailable-engine responses without binding a port.

`test_extraction_models.py` validates nullable invoice fields, dates, decimals,
confidence bounds, evidence references, and schema strictness.

`test_extraction_protocol.py` validates that OCR pages and image pages align.
`test_extraction_graph.py` exercises the single typed LangGraph node with a fake
extractor. `test_extraction_service.py` proves the service passes both OCR text
and normalized page images into that graph.

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

## Fixtures

Fixtures are generated by `tests/fixtures/fictional_invoice.py` from
fixed inputs. They contain fictional vendor, invoice, purchase-order, and total
text only, and their output is asserted deterministic.

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
fake `OCREngine`. Responses adapter tests use a fake client, while graph,
service, and API tests inject a fake `StructuredExtractor`. Verification tests
use the `InvoiceRepository` boundary or a temporary SQLite file. Tests must not
require API keys, network access, an installed OCR executable, or
machine-specific configuration.

Mock at the typed boundary protocol rather than patching deep vendor internals.
Keep deterministic decoding, validation, and Pydantic schema validation real;
replace only external OCR or model execution.

## Quality checks

Run lint and formatting checks with the tests:

```bash
uv run ruff check .
uv run ruff format --check .
```

No static type checker or coverage threshold is configured in Phase 3. Do not
claim either gate exists. Type hints remain required, and coverage should focus
on meaningful success, boundary, and error behavior rather than a percentage
alone.

## Required evidence by change type

| Change | Minimum focused evidence |
| --- | --- |
| Documentation only | Verify paths, commands, examples, and links |
| Validation or decoder module | Focused success/error pytest, Ruff lint, Ruff format check |
| OCR adapter or service | Mocked boundary tests, Ruff lint, Ruff format check |
| Extraction schema, graph, or adapter | Typed-boundary tests, mocked provider tests, Ruff lint, Ruff format check |
| Persistence adapter | Temporary SQLite integration tests, Ruff lint, Ruff format check |
| Verification rule, service, or graph | Normal/anomalous synthetic tests, Ruff lint, Ruff format check |
| API behavior or schema | Success and relevant error/contract tests |
| Dependency or lockfile | `uv lock --check`, full pytest, applicable quality checks |
| Phase completion | Clean sync, isolated import, full pytest, lint, format, runtime smoke test, clean Git status |

Run the full suite before completing a phase even when every individual commit
already had a focused check. See `AGENTS.md` for staging and commit rules and
`docs/development.md` for the development workflow.
