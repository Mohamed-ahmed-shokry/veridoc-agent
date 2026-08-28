# Veridoc

Veridoc is an invoice and purchase-order intelligence system designed to answer
a question that OCR alone cannot: **is the extracted document data trustworthy?**

Veridoc validates one invoice image or PDF, runs a replaceable Tesseract OCR
baseline, and returns either raw page text or typed evidence-linked extraction
through a replaceable OpenAI Responses adapter. It also supplies local SQLite
reference persistence, typed deterministic verification, and an internal
evidence-grounded explanation layer. `POST /process` now returns the complete
typed result with findings, explanations, and a deterministic review verdict;
`GET /review` supplies a minimal local display surface for that result. The
final integration pass adds request correlation and end-to-end dependency-graph
coverage without changing the deliberately local product boundary. Phase 8 adds
authenticated local administration, forward-only SQLite migrations, bounded
atomic imports, and safe backup/restore tooling for approved reference facts.
Phase 9 adds a per-actor authenticated review workflow: an immutable,
digest-verified processing snapshot and append-only event history per case,
in a dedicated local SQLite store, behind session cookies, CSRF protection,
and role-scoped authorization, plus a browser console at `/review/console`.

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
- Bearer-authenticated invoice and purchase-order reference-data CRUD with
  canonical vendor keys and matching list filters;
- bounded atomic JSON imports with explicit reject, skip, replace, and dry-run
  behavior;
- numbered forward-only SQLite migrations with provenance and optional retention
  metadata;
- non-mutating online backup with integrity, migration, and constraint validation,
  plus stopped-service atomic restore tooling;
- safe `X-Request-ID` correlation and metadata-only request completion logs;
- deterministic fictional invoice fixtures and focused error-path tests;
- Ruff lint and format checks;
- per-actor authenticated review sessions with `HttpOnly`/`Secure` cookies,
  double-submit CSRF protection, and two roles (`reviewer`, `review_admin`);
- immutable, schema-versioned, digest-verified per-case processing snapshots
  with an append-only event history, in a dedicated local SQLite store;
- optimistic-concurrency and idempotency-key guarded case creation,
  assignment/reassignment, escalation, and terminal decisions;
- a build-free browser console at `/review/console` that renders every
  fetched value through DOM text nodes only; and
- a separate `veridoc-review` backup/restore maintenance command.

## Quick start

Prerequisites:

- Git
- [uv](https://docs.astral.sh/uv/) 0.9.13 (required by `pyproject.toml`)
- Tesseract OCR executable with the trained data for requested languages
- an OpenAI API key and vision-capable model when using `POST /extract` or
  `POST /process`
- a randomly generated 32-256 character token when using reference-data
  administration
- an operator-managed actor file and an HTTPS review origin when using the
  review workflow

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

Configure the local reference database separately for processing,
administration, and maintenance. The administration token is required only for
`/admin/reference-data/*` routes:

```powershell
$env:VERIDOC_REFERENCE_DATABASE = "veridoc-reference.sqlite3"
$env:VERIDOC_ADMIN_TOKEN = "replace-with-a-random-token-at-least-32-characters"
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
$env:TESSERACT_TIMEOUT_SECONDS = "30"
```

Blank language settings and nonnumeric, nonfinite, nonpositive, or greater-than-
300-second timeouts return the same safe `ocr_unavailable` 503 as an unavailable
Tesseract executable.

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

Uploads are limited to 10 MiB with 64 KiB reserved for multipart framing, 20 PDF
pages, 20,000,000 pixels per decoded/rendered page, and 50,000,000 rendered
pixels across a PDF. Invalid documents are rejected before OCR, provider, or
repository construction. The declared content type must match the validated
signature. See the [API guide](docs/api.md) for the complete error contract.

## Structured extraction request

With `OPENAI_API_KEY` and `VERIDOC_LLM_MODEL` configured, submit the same
validated multipart document to `/extract`:

```bash
curl.exe -X POST http://127.0.0.1:8000/extract \
  -F "file=@fictional-invoice.png;type=image/png"
```

The typed response preserves absent fields as `null`, reports OCR and extraction
confidence separately, and returns page/source evidence plus uncertainty rather
than fabricating missing data. Extracted quantities and amounts are limited to
24 digits with at most 6 decimal places. Every evidence page must exist, and a
supplied OCR text span must occur on that page after Unicode, case, and
whitespace normalization. Normalized page images are limited to 32 MiB in
aggregate before provider input. Each extraction or explanation provider call
has a fixed 120-second application deadline; extraction expiry returns a safe
503 and explanation expiry falls back to deterministic guidance. See the [API
guide](docs/api.md) for the complete schema, limits, and error responses.

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

## Reference-data administration

With `VERIDOC_ADMIN_TOKEN` configured in the API process, local operators can
create, list, read, update, delete, and atomically import typed invoice and
purchase-order reference facts under `/admin/reference-data/*`. Send the token
only in the Bearer header:

```powershell
curl.exe http://127.0.0.1:8000/admin/reference-data/invoices `
  -H "Authorization: Bearer $env:VERIDOC_ADMIN_TOKEN"
```

Each record carries immutable source/external identifiers, server timestamps,
and optional retention metadata. Create/update JSON bodies and import files are
limited to 1 MiB before parsing, imports contain at most 500 total records, and
each record is limited to 200 line items. The shared token is a local control,
not user identity or production authorization. See the [API guide](docs/api.md)
for payloads and conflict behavior.

Create an online backup with the maintenance entry point:

```powershell
uv run veridoc-reference `
  --database veridoc-reference.sqlite3 `
  backup --output backups/reference-data.backup.sqlite
```

The backup preserves the source database's schema version. Validation and any
supported migration run only on a disposable copy; every stored fact, metadata
field, and attached line item must satisfy the bounded persistence contract
before the original snapshot is published.

Restore requires a stopped service and explicit `--confirm-replace`; see the
[development guide](docs/development.md) before replacing a database.

## Review workflow

Configure an operator-managed actor file and an HTTPS review origin, then
open the console:

```powershell
$env:VERIDOC_REVIEW_ACTORS_FILE = "C:\secure\veridoc-review-actors.json"
$env:VERIDOC_REVIEW_ORIGIN = "https://review.example"
```

Authenticate with an actor's credential to receive a session cookie:

```powershell
curl.exe -X POST "$env:VERIDOC_REVIEW_ORIGIN/review/session" `
  -H "Authorization: Bearer <actor-secret>" `
  -H "Origin: $env:VERIDOC_REVIEW_ORIGIN"
```

`POST /review/cases` runs the same processing pipeline as `/process` and
stores the typed result as a new case's immutable snapshot. Every
subsequent claim, assignment, escalation, or decision appends one
`Idempotency-Key`- and `expected_version`-guarded event; nothing is ever
edited in place. Open `$env:VERIDOC_REVIEW_ORIGIN/review/console` through the
configured HTTPS-serving proxy for the authenticated login, case list,
evidence, and action console. See the [API guide](docs/api.md) for the complete
route family, and
[architecture](docs/architecture.md) for the case status/transition model.

## Tests and quality checks

Run the complete suite:

```bash
uv run pytest
```

Run representative focused Phase 1 through Phase 9 tests:

```bash
uv run pytest tests/test_ingestion_validation.py
uv run pytest tests/test_request_body_limits.py
uv run pytest tests/test_upload_dependency_order.py
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
uv run pytest tests/test_documentation.py
uv run pytest tests/test_administration_auth.py
uv run pytest tests/test_sqlite_migrations.py
uv run pytest tests/test_administration_sqlite_import.py
uv run pytest tests/test_administration_invoice_api.py
uv run pytest tests/test_reference_data_maintenance.py
uv run pytest tests/test_administration_cli.py
uv run pytest tests/test_review_transitions.py
uv run pytest tests/test_review_sqlite_repository.py
uv run pytest tests/test_review_persistence_concurrency.py
uv run pytest tests/test_review_session_api.py
uv run pytest tests/test_review_case_creation_api.py
uv run pytest tests/test_review_case_assignment_api.py
uv run pytest tests/test_review_api_error_contracts.py
uv run pytest tests/test_review_console_page.py
uv run pytest tests/test_review_case_creation_integration.py
uv run pytest tests/test_review_authorization_integration.py
uv run pytest tests/test_review_retry_recovery_integration.py
```

See the [testing guide](docs/testing.md) for the complete Phase 9 test list.

Run lint and formatting checks:

```bash
uv run ruff check .
uv run ruff format --check .
```

Run the Phase 7 release-engineering gates:

```bash
uv run mypy
uv run pytest --cov=veridoc
uv lock --check
uv run pip-audit
uv build --clear
uv run twine check dist/*
uv run python scripts/check_distribution.py
```

The coverage gate measures branches and fails below 90%. See the
[testing guide](docs/testing.md) for focused-test boundaries and the
[development guide](docs/development.md) for package and isolated-artifact checks.

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
without persistence or workflow actions. A separate authenticated administration
adapter manages approved reference facts through the repository protocol;
processing-domain logic does not import FastAPI or SQLite connection code. The
API also returns an `X-Request-ID` for safe operational correlation. See
[architecture](docs/architecture.md) for boundaries and tradeoffs.

## Repository structure

```text
.
├── .github/
│   └── workflows/
│       └── ci.yml
├── AGENTS.md
├── CHANGELOG.md
├── README.md
├── docs/
│   ├── api.md
│   ├── architecture.md
│   ├── data-and-security.md
│   ├── development.md
│   ├── phase-9-plan.md
│   ├── release-evidence.md
│   ├── roadmap.md
│   ├── testing.md
│   └── decisions/
│       ├── README.md
│       ├── 0001-use-tesseract-for-v1.md
│       ├── 0002-use-openai-responses-for-phase-2.md
│       ├── 0003-use-sqlite-for-phase-3-reference-data.md
│       ├── 0004-use-validated-llm-proposals-for-explanations.md
│       ├── 0005-use-review-required-processing-verdicts.md
│       ├── 0006-use-bearer-token-for-local-administration.md
│       ├── 0007-use-forward-only-sqlite-migrations.md
│       ├── 0008-use-local-actor-file-and-http-only-sessions-for-review.md
│       ├── 0009-use-immutable-versioned-review-records.md
│       └── 0010-defer-automated-review-retention-and-purge.md
├── src/
│   └── veridoc/
│       ├── administration/
│       ├── extraction/
│       ├── ingestion/
│       ├── ocr/
│       ├── persistence/
│       ├── verification/
│       ├── explanation/
│       ├── processing/
│       ├── review/
│       │   ├── persistence/     dedicated review SQLite store, migrations, CLI
│       │   ├── api.py           authenticated FastAPI router
│       │   ├── console_page.py  no-build authenticated review console
│       │   └── page.py          no-build unauthenticated /review demo page
│       ├── __init__.py
│       ├── __main__.py
│       └── app.py
├── scripts/
│   ├── check_distribution.py
│   └── smoke_distribution.py
├── tests/
│   ├── fixtures/
│   │   └── README.md
│   └── test_*.py
├── .env.example
├── .gitattributes
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
| `TESSERACT_TIMEOUT_SECONDS` | `30` | Per-page OCR timeout from greater than 0 through 300 seconds |
| `OPENAI_API_KEY` | none | Required credential for `/extract` and `/process`; optional explanation guidance also uses it |
| `VERIDOC_LLM_MODEL` | none | Required Responses model for `/extract` and `/process`; optional explanation guidance also uses it |
| `VERIDOC_REFERENCE_DATABASE` | `veridoc-reference.sqlite3` | Local SQLite path for processing and reference-data administration |
| `VERIDOC_ADMIN_TOKEN` | none | Required Bearer token for `/admin/reference-data/*` only |
| `VERIDOC_REVIEW_ACTORS_FILE` | none | Required path to the operator-managed review actor file |
| `VERIDOC_REVIEW_ORIGIN` | none | Required exact HTTPS browser origin for `/review/*` |
| `VERIDOC_REVIEW_DATABASE` | `veridoc-review.sqlite3` | Local SQLite path for the dedicated review store |

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
| 7 | Release engineering and reproducible quality gates | Complete |
| 8 | Controlled reference-data administration | Complete |
| 9 | Persistent, authenticated review and audit workflow | Complete |
| 10 | Deployment and operational security | Planned; not approved |
| 11 | Evaluation, performance, and production-readiness decision | Planned; not approved |

Version 1 processing behavior is complete through Phase 6. Phase 7 strengthened
release evidence without adding endpoints or processing features. Phase 8
completed controlled local reference-data operations with a verified release
gate. Phase 9 completed a per-actor authenticated review workflow with
immutable snapshots, an event history, and a browser console, with its own
verified release gate. See the [project roadmap](docs/roadmap.md) for
deliverables and approval boundaries. The approved design and exact atomic
implementation sequence are in the
[Phase 9 approval plan](docs/phase-9-plan.md); Phases 10 and 11 remain
unapproved.

## Documentation

- [Changelog](CHANGELOG.md): completed version scope and unreleased changes.
- [Development](docs/development.md): setup, commands, Tesseract configuration,
  logging, and atomic workflow.
- [Testing](docs/testing.md): test organization, fixtures, mocks, and quality gates.
- [Architecture](docs/architecture.md): current boundaries and planned phases.
- [Data and security](docs/data-and-security.md): fixture, secret, logging,
  upload, temporary-file, and retention rules.
- [API](docs/api.md): implemented endpoints, limits, examples, and errors.
- [Roadmap](docs/roadmap.md): completed Phase 0 through Phase 9 scope and the
  unapproved Phase 10 and Phase 11 candidates.
- [Phase 9 delivery plan](docs/phase-9-plan.md): implemented design, decisions,
  atomic delivery record, verified gates, and the later-phase approval boundary.
- [Release evidence](docs/release-evidence.md): verified local gates and evidence
  boundaries.
- [Decision records](docs/decisions/README.md): ADR format and index.
- [Agent guide](AGENTS.md): repository-specific rules for coding agents.

## Current limitations

Veridoc does not yet provide authoritative vendor identity resolution, token
rotation, malware scanning, encrypted storage, a compliance-grade durable
audit log, TLS termination, or remote/production deployment controls. Phase 8
authenticates local reference-data administration with one shared token;
Phase 9 authenticates the review workflow per actor with session cookies and
two roles, but its actor file is local and operator-managed with no
self-registration, password reset, or remote directory integration, and it
performs no automated retention/purge or case deletion (ADR 0010). `/ocr`,
`/extract`, `/process`, and the older `/review` demo page remain
unauthenticated. The deterministic `clear` verdict means only that no
implemented rule produced a finding; it is not an automated approval, and
neither is a review case's `decided` status. The service remains a local
development boundary and is not production ready.

## Future work

Phase 9 completed a persistent, authenticated review/audit workflow after
Phase 8's reference-data administration. Later candidates cover deployment
security (including a production-grade identity provider and TLS profile)
and evidence-based readiness evaluation. They are documented in the
[roadmap](docs/roadmap.md) but remain unapproved and unimplemented.
