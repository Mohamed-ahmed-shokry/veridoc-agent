# Development

This guide covers the implemented Phase 1 upload and OCR boundary. Structured
invoice extraction, graph orchestration, verification, persistence, and the LLM
boundary remain unimplemented.

## Prerequisites

- Git
- [uv](https://docs.astral.sh/uv/)
- a platform supported by Python 3.12
- Tesseract OCR executable and trained data for local OCR requests

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
│   ├── __main__.py            console entry point
│   └── app.py                FastAPI application and endpoints
├── tests/
│   ├── fixtures/             deterministic fictional invoice generators
│   ├── test_ingestion_*.py   validation and cleanup tests
│   ├── test_ocr_*.py         OCR contracts, service, and API tests
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

Phase 1 runtime dependencies are FastAPI, python-multipart, Pillow, PyMuPDF,
pytesseract, and Uvicorn. Do not add a second OCR engine or future graph,
extraction, LLM, or database dependency.

After a dependency change, verify resolution and the complete suite:

```bash
uv lock --check
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Configuration

Phase 1 has two optional process environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `TESSERACT_CMD` | executable found on `PATH` | Explicit Tesseract executable path |
| `TESSERACT_LANG` | `eng` | Tesseract language or language combination |

The application does not load `.env` files. Set variables in the process
environment or an approved secret/configuration provider; keep `.env.example`
safe and non-secret.

## Logging and data handling

Uvicorn owns basic request and lifecycle logs. The OCR boundary does not log
document bodies, raw OCR text, extracted values, credentials, temporary paths,
or Tesseract output. Uploaded bytes are private and ephemeral for one request;
the temporary directory is removed after success or failure.

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
4. Keep external executable failures mapped to safe public errors.
5. Add deterministic synthetic fixtures only when a focused test needs them.
6. Run focused lint, format, import, and test checks.
7. Update the affected documentation in the same commit when inseparable or in
   the immediately following focused documentation commit.
8. Update `AGENTS.md` if commands, package boundaries, conventions, or required
   checks changed.
