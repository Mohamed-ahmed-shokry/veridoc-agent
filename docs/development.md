# Development

This guide covers the implemented Phase 0 scaffold. Later-phase services and
commands are intentionally absent.

## Prerequisites

- Git
- [uv](https://docs.astral.sh/uv/)
- a platform supported by Python 3.12

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

## Run the service

Start the development server with reload support:

```bash
uv run uvicorn veridoc.app:app --reload
```

The service listens on `http://127.0.0.1:8000` by default. Verify it from a
second PowerShell session:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

The expected object has one property, `status`, with value `ok`.

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
├── docs/
│   ├── decisions/README.md   ADR policy and index
│   └── development.md        this guide
├── src/veridoc/
│   ├── __init__.py           package metadata
│   ├── __main__.py           console entry point
│   └── app.py                FastAPI app and health endpoint
├── tests/
│   ├── test_app.py           application import and metadata test
│   └── test_health.py        health behavior and schema tests
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

Replace `PACKAGE` with one package name. Do not add a bundle of anticipated
future dependencies.

After a dependency change, verify resolution and the complete suite:

```bash
uv lock --check
uv run pytest
uv run ruff check .
uv run ruff format --check .
```

## Configuration

Phase 0 has no required application settings. `.env.example` records that fact;
the application does not load a `.env` file.

When a later approved phase introduces configuration:

1. read values from the environment at the external boundary;
2. validate required values at startup with clear errors;
3. add only safe placeholders to `.env.example`;
4. keep real `.env` files untracked; and
5. document every supported variable with the related implementation.

Never commit credentials, model keys, database secrets, or service tokens.

## Logging

Phase 0 relies on Uvicorn's standard request and lifecycle logs. Veridoc does not
yet configure an application logging layer. Do not claim structured document
processing logs exist.

When I/O stages are approved, logs should carry a correlation identifier and
stage name, distinguish retryable external failures, and exclude document
bodies, extracted sensitive values, credentials, and secrets.

## Development workflow

Before changing code:

```bash
git status --short
uv run pytest
```

For one small change, run the narrowest relevant tests and checks, inspect the
diff, and stage only its named files. For example, a change limited to the health
tests uses:

```bash
uv run pytest tests/test_health.py
uv run ruff check tests/test_health.py
uv run ruff format --check tests/test_health.py
git status --short
git diff -- tests/test_health.py
git add tests/test_health.py
git diff --staged
git commit -m "test: describe the single behavior"
git status --short
```

The final status output must be empty. Never use broad staging, automatic
squashing, rebasing, amending, or unrelated cleanup. See `AGENTS.md` for the
complete atomic-commit protocol.

## Add a module safely

1. Confirm the module belongs to the currently approved phase.
2. Put application code under `src/veridoc/` and keep the module focused on one
   concern.
3. Keep domain calculations free of FastAPI and external-service imports.
4. Put external access behind a typed, mockable boundary when that phase is
   approved.
5. Add focused tests under `tests/` using deterministic data.
6. Run focused lint, format, import, and test checks.
7. Update the affected documentation in the same commit when inseparable or in
   the immediately following focused documentation commit.
8. Update `AGENTS.md` if the package map, commands, conventions, or required
   checks changed.
