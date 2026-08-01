# Veridoc

Veridoc is an invoice and purchase-order intelligence system designed to answer
a question that OCR alone cannot: **is the extracted document data trustworthy?**

Phase 4 validates one invoice image or PDF, runs a replaceable Tesseract OCR
baseline, and returns either raw page text or typed evidence-linked extraction
through a replaceable OpenAI Responses adapter. It also supplies local SQLite
reference persistence, typed deterministic verification, and an internal
evidence-grounded explanation layer. Public verification/explanation delivery
and verdicts remain later phases.

## Why Veridoc

A value can be extracted perfectly and still be suspicious. For example, an
invoice total may match the printed document while being far outside the
vendor's historical range. Veridoc is scoped to reconcile invoices and purchase
orders while keeping deterministic calculations separate from constrained,
optional provider guidance.

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
- normalized in-memory page images paired with OCR text for vision extraction;
- typed invoice, line-item, evidence, uncertainty, and confidence schemas;
- a typed single-node LangGraph extraction flow;
- `POST /extract` using a mockable OpenAI Responses adapter;
- SQLite invoice and purchase-order reference persistence behind a typed protocol;
- deterministic arithmetic, duplicate, purchase-order, and vendor-history checks;
- typed, evidence-rich verification findings with explicit insufficient-history
  handling;
- a typed single-node LangGraph verification flow;
- typed explanation results that preserve canonical verification findings;
- deterministic explanation and numerical-context rendering;
- an optional mockable Responses provider that can propose only constrained
  guidance, with contradiction protection and deterministic fallback;
- a typed single-node LangGraph explanation flow;
- deterministic fictional invoice fixtures and focused error-path tests; and
- Ruff lint and format checks.

## Quick start

Prerequisites:

- Git
- [uv](https://docs.astral.sh/uv/)
- Tesseract OCR executable with the trained data for requested languages
- an OpenAI API key and vision-capable model when using `POST /extract`

From the repository root:

```bash
uv python install 3.12
uv sync --all-groups --locked
```

For structured extraction and optional explanation-provider guidance, configure
an OpenAI API key and a current vision-capable Responses API model in the same
shell:

```powershell
$env:OPENAI_API_KEY = "replace-with-your-key"
$env:VERIDOC_LLM_MODEL = "replace-with-a-vision-capable-model"
```

Start the local API:

```bash
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

## Structured extraction request

With `OPENAI_API_KEY` and `VERIDOC_LLM_MODEL` configured, submit the same
validated multipart document to `/extract`:

```bash
curl.exe -X POST http://127.0.0.1:8000/extract \
  -F "file=@fictional-invoice.png;type=image/png"
```

The typed response preserves absent fields as `null`, reports OCR and extraction
confidence separately, and returns page/source evidence plus uncertainty rather
than fabricating missing data. See the [API guide](docs/api.md) for the complete
schema, limits, and error responses.

## Tests and quality checks

Run the complete suite:

```bash
uv run pytest
```

Run focused Phase 2, Phase 3, and Phase 4 tests:

```bash
uv run pytest tests/test_ingestion_validation.py
uv run pytest tests/test_ocr_service.py
uv run pytest tests/test_ocr_api.py
uv run pytest tests/test_extraction_graph.py
uv run pytest tests/test_openai_responses.py
uv run pytest tests/test_extraction_api.py
uv run pytest tests/test_sqlite_repository.py
uv run pytest tests/test_verification_service.py
uv run pytest tests/test_verification_graph.py
uv run pytest tests/test_explanation_fallback.py
uv run pytest tests/test_explanation_guardrails.py
uv run pytest tests/test_explanation_service.py
uv run pytest tests/test_openai_explanations.py
uv run pytest tests/test_explanation_graph.py
```

Run lint and formatting checks:

```bash
uv run ruff check .
uv run ruff format --check .
```

No static type checker or coverage threshold is configured in Phase 4. See the
[testing guide](docs/testing.md) for test boundaries and required evidence.

## Architecture

```text
multipart upload -> validation -> temporary file -> page decode
    -> OCREngine -> Tesseract -> typed OCRResponse
    -> OCR text + normalized page images -> extraction graph
    -> StructuredExtractor -> typed InvoiceExtraction
    -> verification graph -> VerificationService -> internal VerificationResult
    -> explanation graph -> ExplanationService -> internal ExplanationResult
```

The implemented internal flow now reaches explanation; a final verdict remains
planned:

```text
ingestion -> OCR -> structured extraction -> verification -> explanation -> verdict
```

The HTTP API remains extraction-only: Phase 4 does not expose verification
findings, explanations, or reference-data management. See
[architecture](docs/architecture.md) for boundaries and tradeoffs.

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
│       ├── 0001-use-tesseract-for-v1.md
│       ├── 0002-use-openai-responses-for-phase-2.md
│       ├── 0003-use-sqlite-for-phase-3-reference-data.md
│       └── 0004-use-validated-llm-proposals-for-explanations.md
├── src/
│   └── veridoc/
│       ├── extraction/
│       ├── ingestion/
│       ├── ocr/
│       ├── persistence/
│       ├── verification/
│       ├── explanation/
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

The current HTTP application reads these process environment variables:

| Variable | Default | Purpose |
| --- | --- | --- |
| `TESSERACT_CMD` | executable on `PATH` | Tesseract executable path |
| `TESSERACT_LANG` | `eng` | Tesseract language or combination |
| `OPENAI_API_KEY` | none | Required credential for `/extract` and an optional explanation adapter |
| `VERIDOC_LLM_MODEL` | none | Required Responses model for `/extract` and an optional explanation adapter |

The application does not load `.env`. Never commit real credentials, invoices,
production documents, personal information, customer data, or confidential
business data. Tests use deterministic fictional fixtures only. See [data and
security](docs/data-and-security.md).

## Phase roadmap

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Repository, FastAPI health scaffold, tests, initial documentation | Complete |
| 1 | Safe invoice ingestion and one OCR baseline | Complete |
| 2 | Typed invoice extraction and LangGraph state/node | Complete |
| 3 | SQLite reference repository and deterministic/statistical verification | Complete |
| 4 | Evidence-grounded explanation layer | Complete |
| 5 | Complete processing API and minimal review interface | Not approved |
| 6 | Final integration, documentation, and operational pass | Not approved |

Work stops after Phase 4 until Phase 5 is explicitly approved.

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

Veridoc does not yet provide authoritative vendor identity resolution, a public
verification, explanation, or reference-data API, a final verdict,
authentication, request correlation, malware scanning, or a review interface.
The extraction endpoint remains a local Phase 2 boundary and is not production
ready.
