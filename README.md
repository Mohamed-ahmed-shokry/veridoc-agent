# Veridoc

Veridoc verifies invoice and purchase-order data. Phase 0 provides a small,
typed FastAPI service foundation; extraction and verification capabilities are
introduced in later phases.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)

## Setup

```bash
uv sync --all-groups
```

## Run the API

```bash
uv run uvicorn veridoc.app:app --reload
```

The health endpoint is available at `http://127.0.0.1:8000/health`.

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected response:

```json
{"status":"ok"}
```

## Run checks

```bash
uv run pytest
uv run ruff check .
```

## Configuration

No configuration values are required in Phase 0. Copy `.env.example` when a
later phase introduces environment-based configuration; never commit `.env`.
