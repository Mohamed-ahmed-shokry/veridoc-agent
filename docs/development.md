# Development

This guide covers product behavior implemented through Phase 6 and the approved
Phase 7 release-engineering workflow. Approval workflows and persistent review
records remain unimplemented.

## Prerequisites

- Git
- [uv](https://docs.astral.sh/uv/)
- a platform supported by Python 3.12
- Tesseract OCR executable and trained data for local OCR requests
- an OpenAI API key and a current vision-capable Responses API model for
  `POST /extract`, `POST /process`, and optional explanation-provider guidance

The repository pins Python 3.12 in `.python-version`. Let uv install it when it
is not already available:

```bash
uv python install 3.12
```

Do not create or manage this project with pip, Conda, Poetry, or Pipenv.

## Environment setup

From the repository root, create or synchronize the virtual environment from
the committed lockfile:

```bash
uv sync --all-groups --locked
```

`--all-groups` installs the development tools used by tests and quality checks.
`--locked` fails instead of silently changing `uv.lock`.

## Tesseract setup

Phase 1 uses one OCR engine: Tesseract through `pytesseract`. Install the
executable separately from Python dependencies. On Windows, install Tesseract
OCR with English data, add its directory to `PATH`, or set the executable path
explicitly:

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
```

For bilingual Arabic and Latin invoices, install the Arabic trained data and
configure:

```powershell
$env:TESSERACT_LANG = "eng+ara"
```

The verified Windows winget installation command is:

```powershell
winget install --id UB-Mannheim.TesseractOCR --exact --accept-source-agreements --accept-package-agreements
```

The default language is `eng`. On Debian or Ubuntu, install `tesseract-ocr`,
`tesseract-ocr-eng`, and `tesseract-ocr-ara` with the system package manager.
The API returns `ocr_unavailable` rather than fabricating text when the
executable or requested language data is absent. See [ADR 0001](decisions/0001-use-tesseract-for-v1.md)
for the decision and limitations.

## Run the service

Start the development server with reload support:

```bash
uv run uvicorn veridoc.app:app --reload
```

The service listens on `http://127.0.0.1:8000`. Verify process health from a
second PowerShell session:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Run a local OCR request with a fictional invoice:

```powershell
curl.exe -X POST http://127.0.0.1:8000/ocr `
  -F "file=@fictional-invoice.png;type=image/png"
```

Configure extraction in the same process before calling `/extract`:

```powershell
$env:OPENAI_API_KEY = "replace-with-your-key"
$env:VERIDOC_LLM_MODEL = "replace-with-a-vision-capable-model"
$env:VERIDOC_REFERENCE_DATABASE = "veridoc-reference.sqlite3"
```

Then submit the same bounded multipart upload:

```powershell
curl.exe -X POST http://127.0.0.1:8000/extract `
  -F "file=@fictional-invoice.png;type=image/png"
```

`/ocr` does not require OpenAI configuration. `/extract` validates the provider
configuration when that route is invoked and returns a safe 503 error if it is
missing or unavailable.

`/process` uses the same extraction settings, initializes the configured local
SQLite reference-data path, and produces deterministic explanation fallback when
optional explanation guidance cannot be configured. Submit the same bounded
upload with:

```powershell
curl.exe -X POST http://127.0.0.1:8000/process `
  -F "file=@fictional-invoice.png;type=image/png"
```

Open `http://127.0.0.1:8000/review` for the small local form that submits to
`/process` and renders its result. It is stateless: it creates no review record
or approval action.

The installed console entry point starts the same application without reload:

```bash
uv run veridoc
```

Stop either process with `Ctrl+C`.

## Project layout

```text
.
├── AGENTS.md                 coding-agent operating rules
├── README.md                 project entry point
├── docs/                     architecture, API, testing, and security guidance
├── src/veridoc/
│   ├── ingestion/            bounded upload validation and temporary storage
│   ├── ocr/                  typed boundary, decoder, and Tesseract adapter
│   ├── extraction/           typed schema, graph, provider protocol, and adapter
│   ├── persistence/          repository protocol and SQLite adapter
│   ├── verification/         deterministic rules, service, and graph
│   ├── explanation/          fallback, provider boundary, service, and graph
│   ├── processing/           complete graph, service, final result, and verdict
│   ├── review/               no-build local review page
│   ├── __main__.py            console entry point
│   └── app.py                FastAPI application and endpoints
├── tests/
│   ├── fixtures/             deterministic fictional invoice generators
│   ├── test_ingestion_*.py   validation and cleanup tests
│   ├── test_ocr_*.py         OCR contracts, service, and API tests
│   ├── test_extraction_*.py  extraction contracts, graph, service, and API tests
│   ├── test_sqlite_repository.py  SQLite reference-data integration tests
│   ├── test_verification_*.py     deterministic verification tests
│   ├── test_explanation_*.py      explanation contracts, fallback, and graph tests
│   ├── test_openai_explanations.py mocked explanation-provider adapter tests
│   ├── test_processing_*.py  complete graph, API, model, and service tests
│   ├── test_processing_integration.py complete dependency-composition test
│   ├── test_request_context.py correlation header and safe-log tests
│   ├── test_review_page.py   local review-interface route test
│   └── test_health.py         health behavior and schema tests
├── pyproject.toml            project and tool configuration
└── uv.lock                   reproducible dependency resolution
```

## Dependencies

Add only a package needed by the currently approved phase. Use one focused
dependency command and commit `pyproject.toml` with `uv.lock`:

```bash
uv add PACKAGE
uv add --dev PACKAGE
```

Phase 6 runtime dependencies are FastAPI, python-multipart, Pillow, PyMuPDF,
pytesseract, Uvicorn, LangGraph, and the OpenAI Python SDK. SQLite uses Python's
standard library, so Phase 6 adds no package. Do not add a second OCR engine,
extraction/explanation provider, database dependency, or frontend build system
without approval.

After a dependency change, verify resolution and the complete suite:

```bash
uv lock --check
uv run pytest
uv run ruff check .
uv run ruff format --check .
uv run mypy
```

## Static type checking

Run the strict production type gate with:

```bash
uv run mypy
```

Mypy checks every module under `src/veridoc`. The configuration narrowly ignores
missing type information from PyMuPDF and pytesseract; application code remains
strictly checked. Tests that deliberately pass coercible or invalid values into
Pydantic models are validated by pytest instead of the production type gate.

## Coverage gate

Run the complete branch-aware coverage gate with:

```bash
uv run pytest --cov=veridoc
```

The committed floor is 90%; the Phase 7 baseline that established it was
93.35%. Use ordinary `uv run pytest <focused target>` commands while developing
one behavior, then run the coverage gate before completing cross-cutting or
phase-level work.

## Continuous integration

`.github/workflows/ci.yml` runs on pull requests and pushes to `main`. Its
Ubuntu job synchronizes the committed lockfile, validates the lock, runs Ruff,
mypy, the full coverage gate, builds both distributions, and imports the wheel
in an isolated environment. The suite uses deterministic fakes, so CI requires
no OpenAI credential or installed Tesseract executable.

CI is remote evidence only after GitHub reports the job result. Run the same
documented commands locally before committing; a local pass does not imply that
an unobserved GitHub job passed.

## Configuration

The application has these process environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `TESSERACT_CMD` | executable found on `PATH` | Explicit Tesseract executable path |
| `TESSERACT_LANG` | `eng` | Tesseract language or language combination |
| `OPENAI_API_KEY` | none | Required OpenAI credential for `/extract` and `/process`, plus optional explanation guidance |
| `VERIDOC_LLM_MODEL` | none | Required Responses API model for `/extract` and `/process`, plus optional explanation guidance |
| `VERIDOC_REFERENCE_DATABASE` | `veridoc-reference.sqlite3` | Local SQLite invoice/PO reference-data path used by `/process` |

The application does not load `.env` files. Set variables in the process
environment or an approved secret/configuration provider; keep `.env.example`
safe and non-secret. Never log or commit the API key.

## Local reference persistence

`/process` opens and initializes `SQLiteInvoiceRepository` at
`VERIDOC_REFERENCE_DATABASE`; it does not seed, export, or manage reference
facts. Local integration code can create the schema explicitly:

```python
from veridoc.persistence.sqlite import SQLiteInvoiceRepository

repository = SQLiteInvoiceRepository("local-reference-data.sqlite")
repository.initialize()
```

The repository stores invoice history and purchase orders for deterministic
comparison. Use only fictional or otherwise approved reference data. SQLite
files are ignored by Git; see [data and security](data-and-security.md) and
[ADR 0003](decisions/0003-use-sqlite-for-phase-3-reference-data.md).

## Operational guidance

`GET /health` is a liveness check only: it confirms that the API can serve a
request, but does not call Tesseract, OpenAI, or SQLite. For a local startup
check, call it after Uvicorn reports that the process is ready. A `503` from an
OCR, extraction, or reference-data boundary indicates a dependency or
configuration problem; inspect its safe error code and the matching
`X-Request-ID` before retrying. Validation `400`, `413`, and `415` responses
require a different upload rather than an automatic retry. A `422` means the
validated document or typed processing result could not be handled safely.

Every response includes `X-Request-ID`. Clients may submit a bounded safe value
or let the service generate one; do not put invoice numbers, customer data, or
secrets in it. Configure the deployment's standard-library logging to retain the
`veridoc.request` logger at `INFO` when operational request records are needed.
Each record contains only the request ID, HTTP method, path without query text,
status code, and duration in milliseconds.

The OCR, extraction, verification, explanation, processing, and review
boundaries do not log document bodies, raw OCR text, extracted values, rendered
pages, verification findings, explanation narratives, credentials, temporary
paths, Tesseract output, or provider responses. Explanation providers receive
only canonical verification findings and responses are requested with storage
disabled. Uploaded bytes are private and ephemeral for one request; the
temporary directory is removed after success or failure.

## Development workflow

Before changing code:

```bash
git status --short
uv run pytest
```

For one small change, run the narrowest relevant tests and checks, inspect the
diff, stage only its named files, and commit immediately. The final status
output must be empty. Never use broad staging, automatic squashing, rebasing,
amending, or unrelated cleanup. See `AGENTS.md` for the complete atomic commit
protocol.

## Add a module safely

1. Confirm the module belongs to the currently approved phase.
2. Keep upload validation before expensive decoding and OCR.
3. Keep OCR behind the typed `OCREngine` protocol and inject it in tests.
4. Keep structured extraction behind `StructuredExtractor`, and pass only typed
   OCR/page inputs to it.
5. Keep deterministic verification dependent on `InvoiceRepository`, never a
   SQLite connection, FastAPI route, or provider SDK.
6. Keep explanation facts and numerical context derived from
   `VerificationFinding`; providers may propose only constrained guidance.
7. Keep external executable and provider failures mapped to safe public errors
   or deterministic internal fallbacks.
8. Compose only typed stage outputs in `ProcessingState`; derive verdicts from
   canonical findings, never from an LLM response.
9. Keep the review page stateless and render returned data with DOM text nodes.
10. Add deterministic synthetic fixtures only when a focused test needs them.
11. Run focused lint, format, import, and test checks.
12. Update the affected documentation in the same commit when inseparable or in
   the immediately following focused documentation commit.
13. Update `AGENTS.md` if commands, package boundaries, conventions, or required
   checks changed.
