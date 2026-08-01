# Veridoc

Veridoc is an invoice and purchase-order intelligence system designed to answer
a question that OCR alone cannot: **is the extracted document data trustworthy?**

The planned version 1 pipeline will extract invoice facts, compare them with
purchase orders and fictional or approved reference histories, detect logical
and statistical anomalies, and explain each important finding with evidence.

**Current status:** Phase 0 complete. The repository currently provides a typed
FastAPI application and health endpoint only. It does not yet accept documents,
run OCR, extract invoice fields, persist reference data, or detect anomalies.

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
- generated OpenAPI, Swagger UI, and ReDoc pages from FastAPI;
- focused in-process tests for imports, metadata, health behavior, schema, and
  unknown-route errors; and
- Ruff lint and format checks.

## Quick start

Prerequisites:

- Git
- [uv](https://docs.astral.sh/uv/)

From the repository root:

```bash
uv python install 3.12
uv sync --all-groups --locked
uv run uvicorn veridoc.app:app --reload
```

The API starts at `http://127.0.0.1:8000`. Its interactive documentation is at
`http://127.0.0.1:8000/docs`.

The installed console entry point is also available when reload is unnecessary:

```bash
uv run veridoc
```

## Health request

PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Command Prompt, PowerShell, or shell using the curl executable:

```bash
curl.exe http://127.0.0.1:8000/health
```

Response:

```json
{
  "status": "ok"
}
```

See [API documentation](docs/api.md) for the schema, error behavior, and current
upload limitations.

## Tests and quality checks

Run the complete suite:

```bash
uv run pytest
```

Run focused application and health tests:

```bash
uv run pytest tests/test_app.py
uv run pytest tests/test_health.py
```

Run lint and formatting checks:

```bash
uv run ruff check .
uv run ruff format --check .
```

No static type checker or coverage threshold is configured in Phase 0. See the
[testing guide](docs/testing.md) for test boundaries and required evidence.

## Architecture

The implemented system is deliberately small:

```text
Uvicorn entry point -> FastAPI application -> GET /health -> HealthResponse
```

After explicit phase approval, the processing graph will use this flow:

```text
ingestion -> OCR -> structured extraction -> verification -> explanation -> verdict
```

LangGraph, Tesseract, SQLite persistence, and the LLM boundary are fixed version
1 choices or directions but are intentionally not installed or integrated in
Phase 0. See [architecture](docs/architecture.md) for boundaries, dependency
direction, tradeoffs, and planned state flow.

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
│       └── README.md
├── src/
│   └── veridoc/
│       ├── __init__.py
│       ├── __main__.py
│       └── app.py
├── tests/
│   ├── test_app.py
│   └── test_health.py
├── .env.example
├── .gitignore
├── .python-version
├── pyproject.toml
└── uv.lock
```

## Configuration and data

Phase 0 requires no environment variables and does not load `.env`. The tracked
`.env.example` contains safe comments only. Never commit real credentials or
environment files.

No document fixtures are needed yet. Future fixtures must use synthetic or
fictional invoices and vendor histories, deterministic generated data, or an
appropriately licensed public subset. Never commit real invoices, production
documents, personal information, customer data, or confidential business data.
See [data and security](docs/data-and-security.md) for the complete policy.

## Phase roadmap

| Phase | Scope | Status |
| --- | --- | --- |
| 0 | Repository, FastAPI health scaffold, tests, initial documentation | Complete |
| 1 | Safe invoice ingestion and one OCR baseline | Awaiting approval |
| 2 | Typed invoice extraction and LangGraph state/node | Not approved |
| 3 | SQLite reference repository and deterministic/statistical verification | Not approved |
| 4 | Evidence-grounded explanation layer | Not approved |
| 5 | Complete processing API and minimal review interface | Not approved |
| 6 | Final integration, documentation, and operational pass | Not approved |

Work stops after Phase 0 until Phase 1 is explicitly approved.

## Documentation

- [Development](docs/development.md): setup, commands, dependencies, configuration,
  logging, and atomic workflow.
- [Testing](docs/testing.md): test organization, fixtures, mocks, and quality gates.
- [Architecture](docs/architecture.md): current scaffold and planned boundaries.
- [Data and security](docs/data-and-security.md): fixture, secret, logging, upload,
  temporary-file, and retention rules.
- [API](docs/api.md): implemented endpoints and examples.
- [Decision records](docs/decisions/README.md): ADR format and index.
- [Agent guide](AGENTS.md): repository-specific rules for coding agents.

## Current limitations

Veridoc cannot process invoices in Phase 0. There is no upload validation, OCR,
LLM integration, graph, database, anomaly detection, authentication, request
correlation, or review interface. The health check reports process availability
only and does not establish production readiness.
