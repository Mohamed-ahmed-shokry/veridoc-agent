# Testing

Veridoc uses pytest. The Phase 0 suite is intentionally small and verifies the
application object, the health endpoint behavior, and its published response
schema.

## Test organization

Tests live under `tests/`, as configured by `pyproject.toml`:

```text
tests/
├── test_app.py      application import and metadata
└── test_health.py   in-process health endpoint and OpenAPI contract
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

Run the focused health module:

```bash
uv run pytest tests/test_health.py
```

Run one behavior by node ID:

```bash
uv run pytest tests/test_health.py::test_health_check_returns_ok_status
```

Use `-q` locally when compact output is useful. Do not hide failures or warnings
in committed automation.

## Unit and integration boundaries

`tests/test_app.py` is a focused construction test: importing the installed
package must expose a FastAPI object with stable metadata.

`tests/test_health.py` is a narrow in-process API integration test. HTTPX's ASGI
transport calls the FastAPI application directly, so the test exercises routing,
serialization, and status handling without binding a port. Its OpenAPI assertion
separately proves that the named Pydantic response model is part of the public
contract.

As later phases are approved:

- unit-test deterministic domain calculations and validators directly;
- unit-test each LangGraph node with typed state and mocked boundaries;
- test error paths for uploads, OCR, LLM calls, and persistence;
- add a few fixture-based full-graph scenarios; and
- keep live external-service and broad browser suites outside the default MVP
  test run unless they provide unique evidence.

## Fixtures

Phase 0 needs no document fixtures. Future invoice fixtures must be synthetic,
fictional, programmatically generated, or drawn from an appropriately licensed
public subset. They must contain no real customer data, personal information,
credentials, or production documents.

Fixtures should be:

- deterministic across machines and runs;
- minimal for the behavior being tested;
- explicit about expected fields and anomalies;
- independent of wall-clock time unless time is injected; and
- small enough to review in the same commit as their scenario.

Do not invent large fixture collections before a focused test requires them.

## External-service mocking

No external service is called in Phase 0. When boundaries are introduced, inject
typed fakes or mocks for OCR, LLM, remote storage, and similar services. Tests
must not require network access, API keys, local OCR binaries, or a developer's
machine-specific configuration.

Mock at the boundary protocol rather than patching deep vendor internals. Keep
deterministic arithmetic and statistical calculations real; only the external
I/O should be replaced.

## Quality checks

Run lint and formatting checks with the tests:

```bash
uv run ruff check .
uv run ruff format --check .
```

No static type checker or coverage threshold is configured in Phase 0. Do not
claim either gate exists. Type hints remain required, and coverage should focus
on meaningful success, boundary, and error behavior rather than a percentage
alone. Add a coverage tool or type checker only in a focused approved change,
then document and enforce its exact command.

## Required evidence by change type

| Change | Minimum focused evidence |
| --- | --- |
| Documentation only | Verify paths, commands, examples, and links |
| One Python module | Focused pytest target, Ruff lint, Ruff format check |
| API behavior or schema | Success and relevant error/contract tests |
| Dependency or lockfile | `uv lock --check`, full pytest, applicable quality checks |
| Cross-cutting or graph integration | Full pytest plus all configured checks |
| Phase completion | Clean sync, imports, full pytest, lint, format, runtime smoke test, clean Git status |

Run the full suite before completing a phase even when every individual commit
already had a focused check. See `AGENTS.md` for staging and commit rules and
`docs/development.md` for the development workflow.
