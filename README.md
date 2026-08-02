# Veridoc

Veridoc is an invoice and purchase-order intelligence system designed to answer
a question that OCR alone cannot: **is the extracted document data trustworthy?**

Phase 6 validates one invoice image or PDF, runs a replaceable Tesseract OCR
baseline, and returns either raw page text or typed evidence-linked extraction
through a replaceable OpenAI Responses adapter. It also supplies local SQLite
reference persistence, typed deterministic verification, and an internal
evidence-grounded explanation layer. `POST /process` now returns the complete
typed result with findings, explanations, and a deterministic review verdict;
`GET /review` supplies a minimal local display surface for that result. The
final integration pass adds request correlation and end-to-end dependency-graph
coverage without changing the deliberately local product boundary.

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
- a complete typed LangGraph flow from OCR through verdict derivation;
- `POST /process` with safe orchestration and reference-data errors;
- a local, stateless `GET /review` upload and result-display page;
- safe `X-Request-ID` correlation and metadata-only request completion logs;
- deterministic fictional invoice fixtures and focused error-path tests; and
- Ruff lint and format checks.

## Quick start

Prerequisites:

- Git
- [uv](https://docs.astral.sh/uv/)
- Tesseract OCR executable with the trained data for requested languages
- an OpenAI API key and vision-capable model when using `POST /extract` or
  `POST /process`

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
$env:VERIDOC_REFERENCE_DATABASE = "veridoc-reference.sqlite3"
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

## Complete processing and review

With the same extraction configuration, `/process` runs OCR, extraction,
deterministic verification, explanation, and verdict derivation in one request:

```bash
curl.exe -X POST http://127.0.0.1:8000/process \
  -H "X-Request-ID: local-process-example-001" \
  -F "file=@fictional-invoice.png;type=image/png"
```

The typed response includes the extraction, canonical verification findings,
evidence-grounded explanations, and either `clear` or `review_required`. The
service uses `VERIDOC_REFERENCE_DATABASE` (default:
`veridoc-reference.sqlite3`) for local reference lookups; it never stores the
uploaded document or the response. Open `http://127.0.0.1:8000/review` for the
minimal local upload-and-result view. See the [API guide](docs/api.md) for its
full response and error contract.

Every response also includes `X-Request-ID`. Supply a safe opaque identifier to
correlate local logs, or use the generated value returned by the service. Never
use a document number, customer value, or secret as the identifier.

## Tests and quality checks

Run the complete suite:

```bash
uv run pytest
```

Run focused Phase 2 through Phase 6 tests:

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
uv run pytest tests/test_processing_graph.py
uv run pytest tests/test_processing_service.py
uv run pytest tests/test_processing_api.py
uv run pytest tests/test_processing_integration.py
uv run pytest tests/test_request_context.py
uv run pytest tests/test_review_page.py
```

Run lint and formatting checks:

```bash
uv run ruff check .
uv run ruff format --check .
```

No static type checker or coverage threshold is configured in Phase 6. See the
[testing guide](docs/testing.md) for test boundaries and required evidence.

## Architecture

```text
multipart upload -> validation -> temporary file -> page decode
    -> OCREngine -> Tesseract -> typed OCRResponse
    -> OCR text + normalized page images -> extraction graph
    -> StructuredExtractor -> typed InvoiceExtraction
    -> verification graph -> VerificationService -> VerificationResult
    -> explanation graph -> ExplanationService -> explanations
    -> verdict -> typed ProcessingResult
```

`/process` exposes the typed final result, while `/review` renders it locally
without persistence or workflow actions. Reference-data management remains out
of scope. The API also returns an `X-Request-ID` for safe operational
correlation. See [architecture](docs/architecture.md) for boundaries and
tradeoffs.

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
│       ├── 0004-use-validated-llm-proposals-for-explanations.md
│       └── 0005-use-review-required-processing-verdicts.md
├── src/
│   └── veridoc/
│       ├── extraction/
│       ├── ingestion/
│       ├── ocr/
│       ├── persistence/
│       ├── verification/
│       ├── explanation/
│       ├── processing/
│       ├── review/
│       ├── __init__.py
│       ├── __main__.py
│       └── app.py
├── tests/
│   ├── fixtures/
│   │   └── README.md
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
| `OPENAI_API_KEY` | none | Required credential for `/extract` and `/process`; optional explanation guidance also uses it |
| `VERIDOC_LLM_MODEL` | none | Required Responses model for `/extract` and `/process`; optional explanation guidance also uses it |
| `VERIDOC_REFERENCE_DATABASE` | `veridoc-reference.sqlite3` | Local SQLite path for `/process` reference lookups |

The application does not load `.env`. Never commit real credentials, invoices,
production documents, personal information, customer data, or confidential
business data. Tests use deterministic fictional fixtures only; see the
[fixture-generation guide](tests/fixtures/README.md) before adding one. See
[data and security](docs/data-and-security.md) for the full policy.

## Phase roadmap

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Repository, FastAPI health scaffold, tests, initial documentation | Complete |
| 1 | Safe invoice ingestion and one OCR baseline | Complete |
| 2 | Typed invoice extraction and LangGraph state/node | Complete |
| 3 | SQLite reference repository and deterministic/statistical verification | Complete |
| 4 | Evidence-grounded explanation layer | Complete |
| 5 | Complete processing API and minimal review interface | Complete |
| 6 | Final integration, documentation, and operational pass | Complete |
| 7 | Release engineering and reproducible quality gates | Approved; in progress |
| 8 | Controlled reference-data administration | Planned; not approved |
| 9 | Persistent review and audit workflow | Planned; not approved |
| 10 | Deployment and operational security | Planned; not approved |
| 11 | Evaluation, performance, and production-readiness decision | Planned; not approved |

Version 1 product behavior is complete through Phase 6. Phase 7 strengthens the
release evidence without adding endpoints or processing features. See the
[project roadmap](docs/roadmap.md) for phase deliverables and approval boundaries.

## Documentation

- [Development](docs/development.md): setup, commands, Tesseract configuration,
  logging, and atomic workflow.
- [Testing](docs/testing.md): test organization, fixtures, mocks, and quality gates.
- [Architecture](docs/architecture.md): current boundaries and planned phases.
- [Data and security](docs/data-and-security.md): fixture, secret, logging,
  upload, temporary-file, and retention rules.
- [API](docs/api.md): implemented endpoints, limits, examples, and errors.
- [Roadmap](docs/roadmap.md): approved Phase 7 work and unapproved later phases.
- [Decision records](docs/decisions/README.md): ADR format and index.
- [Agent guide](AGENTS.md): repository-specific rules for coding agents.

## Current limitations

Veridoc does not yet provide authoritative vendor identity resolution,
reference-data management, authentication, malware scanning, a persistent audit
log, or a persistent/authenticated review workflow. The deterministic `clear`
verdict means only that no implemented rule produced a finding; it is not an
automated approval. The service remains a local development boundary and is not
production ready.

## Future work

Phase 7 is limited to release engineering. Later candidates cover controlled
reference-data administration, persistent review/audit workflows, deployment
security, and evidence-based readiness evaluation. They are documented in the
[roadmap](docs/roadmap.md) but remain unapproved and unimplemented.
