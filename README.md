# Veridoc

Veridoc is an invoice and purchase-order intelligence system designed to answer
a question that OCR alone cannot: **is the extracted document data trustworthy?**

Phase 1 now validates one invoice image or PDF, runs a replaceable Tesseract OCR
baseline, and returns raw page text with optional confidence. Structured field
extraction, reference comparison, anomaly detection, explanations, and verdicts
remain later phases.

## Why Veridoc

A value can be extracted perfectly and still be suspicious. For example, an
invoice total may match the printed document while being far outside the
vendor's historical range. Veridoc is scoped to reconcile invoices and purchase
orders while keeping deterministic calculations separate from later LLM-based
interpretation.

It is not a generic upload-and-extract platform, KYC system, accounting system
of record, or autonomous payment approver.

## Implemented capabilities

- installable Python 3.12 package managed and locked with uv;
- FastAPI application with stable title and version metadata;
- typed `HealthResponse` contract for `GET /health`;
- bounded PDF, PNG, and JPEG upload validation using content signatures;
- safe filename normalization, page/pixel limits, and private temporary cleanup;
- typed `OCREngine` boundary with Tesseract adapter and `TESSERACT_LANG` support;
- sequential PDF page rasterization and RGB image decoding;
- `POST /ocr` raw OCR response with page text and optional confidence;
- deterministic fictional invoice fixtures and focused error-path tests; and
- Ruff lint and format checks.

## Quick start

Prerequisites:

- Git
- [uv](https://docs.astral.sh/uv/)
- Tesseract OCR executable with the trained data for requested languages

From the repository root:

```bash
uv python install 3.12
uv sync --all-groups --locked
uv run uvicorn veridoc.app:app --reload
```

The API starts at `http://127.0.0.1:8000`. Interactive documentation is at
`http://127.0.0.1:8000/docs`.

For Windows, set an explicit executable path when Tesseract is not on `PATH`:

```powershell
$env:TESSERACT_CMD = "C:\Program Files\Tesseract-OCR\tesseract.exe"
$env:TESSERACT_LANG = "eng+ara"
```

The installed console entry point is also available when reload is unnecessary:

```bash
uv run veridoc
```

See [development](docs/development.md) and [ADR 0001](docs/decisions/0001-use-tesseract-for-v1.md)
for executable installation and Arabic/Latin runtime guidance.

## Health request

PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Response:

```json
{
  "status": "ok"
}
```

## OCR request

Submit a fictional invoice image or PDF as the `file` multipart field:

```bash
curl.exe -X POST http://127.0.0.1:8000/ocr \
  -F "file=@fictional-invoice.png;type=image/png"
```

The response contains the detected media type, raw text, optional aggregate
confidence, and one page object per decoded page:

```json
{
  "media_type": "image/png",
  "text": "Fictional Northwind Supplies\nInvoice INV-0001",
  "confidence": 91.5,
  "pages": [
    {
      "page_number": 1,
      "text": "Fictional Northwind Supplies\nInvoice INV-0001",
      "confidence": 91.5
    }
  ]
}
```

Uploads are limited to 10 MiB, 20 PDF pages, and 20,000,000 decoded/rendered
pixels. The declared content type must match the validated signature. See the
[API guide](docs/api.md) for the complete error contract.

## Tests and quality checks

Run the complete suite:

```bash
uv run pytest
```

Run focused Phase 1 tests:

```bash
uv run pytest tests/test_ingestion_validation.py
uv run pytest tests/test_ocr_service.py
uv run pytest tests/test_ocr_api.py
```

Run lint and formatting checks:

```bash
uv run ruff check .
uv run ruff format --check .
```

No static type checker or coverage threshold is configured in Phase 1. See the
[testing guide](docs/testing.md) for test boundaries and required evidence.

## Architecture

```text
multipart upload -> validation -> temporary file -> page decode
    -> OCREngine -> Tesseract -> typed OCRResponse
```

The planned version 1 flow continues after OCR:

```text
ingestion -> OCR -> structured extraction -> verification -> explanation -> verdict
```

LangGraph, a vision-capable LLM, SQLite persistence, and deterministic anomaly
verification are not implemented yet. See [architecture](docs/architecture.md)
for boundaries and tradeoffs.

## Repository structure

```text
.
├── AGENTS.md
├── README.md
├── docs/
│   ├── api.md
│   ├── architecture.md
│   ├── data-and-security.md
│   ├── development.md
│   ├── testing.md
│   └── decisions/
│       ├── README.md
│       └── 0001-use-tesseract-for-v1.md
├── src/
│   └── veridoc/
│       ├── ingestion/
│       ├── ocr/
│       ├── __init__.py
│       ├── __main__.py
│       └── app.py
├── tests/
│   ├── fixtures/
│   └── test_*.py
├── .env.example
├── .gitignore
├── .python-version
├── pyproject.toml
└── uv.lock
```

## Configuration and data

Phase 1 reads two optional process environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `TESSERACT_CMD` | executable on `PATH` | Tesseract executable path |
| `TESSERACT_LANG` | `eng` | Tesseract language or combination |

The application does not load `.env`. Never commit real credentials, invoices,
production documents, personal information, customer data, or confidential
business data. Tests use deterministic fictional fixtures only. See [data and
security](docs/data-and-security.md).

## Phase roadmap

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Repository, FastAPI health scaffold, tests, initial documentation | Complete |
| 1 | Safe invoice ingestion and one OCR baseline | In progress |
| 2 | Typed invoice extraction and LangGraph state/node | Awaiting approval |
| 3 | SQLite reference repository and deterministic/statistical verification | Not approved |
| 4 | Evidence-grounded explanation layer | Not approved |
| 5 | Complete processing API and minimal review interface | Not approved |
| 6 | Final integration, documentation, and operational pass | Not approved |

Work stops after Phase 1 until Phase 2 is explicitly approved.

## Documentation

- [Development](docs/development.md): setup, commands, Tesseract configuration,
  logging, and atomic workflow.
- [Testing](docs/testing.md): test organization, fixtures, mocks, and quality gates.
- [Architecture](docs/architecture.md): current boundaries and planned phases.
- [Data and security](docs/data-and-security.md): fixture, secret, logging,
  upload, temporary-file, and retention rules.
- [API](docs/api.md): implemented endpoints, limits, examples, and errors.
- [Decision records](docs/decisions/README.md): ADR format and index.
- [Agent guide](AGENTS.md): repository-specific rules for coding agents.

## Current limitations

Veridoc does not yet extract structured invoice fields, identify vendors, compare
purchase orders or vendor history, detect anomalies, generate explanations,
persist reference data, authenticate requests, correlate requests, scan for
malware, or provide a review interface. The OCR endpoint is a local Phase 1
boundary and is not production ready.
