# Veridoc Agent Operating Guide

## Project purpose

Veridoc is an agentic document-intelligence system for deciding whether data
extracted from invoices can be trusted. Its version 1 scope is invoice and
purchase-order reconciliation: extraction is only one stage, and later stages
must compare deterministic facts, reference data, and historical behavior before
returning evidence-backed findings.

Veridoc is not a generic document extraction platform. Do not add KYC,
identity-document, speculative model-training, or generic workflow abstractions.
Keep boundaries reusable where the current invoice use case naturally requires
them, and otherwise follow YAGNI.

## Current phase and implementation

Phase 0 is complete. No later phase is approved. The current implementation is
deliberately small:

- `src/veridoc/__init__.py` exposes package metadata.
- `src/veridoc/__main__.py` starts the local API process.
- `src/veridoc/app.py` creates the FastAPI application and exposes `GET /health`.
- `tests/test_app.py` verifies application imports, metadata, and the safe 404
  response.
- `tests/test_health.py` verifies health behavior and its required OpenAPI schema
  without a network server.

OCR, uploads, LangGraph orchestration, structured extraction, persistence,
verification, explanations, and a review interface are not implemented. Do not
add any of them until the user explicitly approves the corresponding phase.

The approved future workflow is:

```text
ingestion -> OCR -> structured extraction -> verification -> explanation -> verdict
```

When those layers are approved, dependencies must point inward: API and graph
orchestration may call domain services and boundary protocols; external OCR,
LLM, and persistence adapters may implement those protocols; domain logic must
not import FastAPI, LangGraph, SQLite connection code, or vendor SDKs.

## Fixed stack

- Use `uv` exclusively for Python versions, dependencies, locking, and commands.
- Use FastAPI for the HTTP API.
- Use LangGraph for the processing graph after its phase is approved; it is not
  installed in Phase 0.
- Tesseract is the selected version 1 OCR baseline. It is not installed or
  integrated in Phase 0. Before Phase 1 code, record the decision, limitations,
  and exact Arabic and Latin installation/runtime instructions in an ADR.
- Use SQLite behind a repository interface when Phase 3 is approved.
- Use pytest for tests.

Do not replace the fixed stack without asking first. Add dependencies only when
the currently approved phase uses them, and commit `pyproject.toml` and `uv.lock`
together.

## Development commands

Run all commands from the repository root.

```bash
# Create or synchronize the environment from the committed lockfile.
uv sync --all-groups --locked

# Start the API locally.
uv run uvicorn veridoc.app:app --reload

# Run the complete test suite.
uv run pytest

# Run the focused health test.
uv run pytest tests/test_health.py

# Check lint and formatting.
uv run ruff check .
uv run ruff format --check .

# Confirm pyproject.toml and uv.lock agree.
uv lock --check

# Apply formatting when needed.
uv run ruff format .
```

No static type checker is configured in Phase 0. When one is introduced, add
its exact command here in the same commit as its configuration.

Add runtime dependencies with `uv add <package>` and development dependencies
with `uv add --dev <package>`. Never use pip, Conda, Poetry, Pipenv, or a
`requirements.txt` file as the primary dependency workflow.

## Atomic commit protocol

Every commit must be the smallest meaningful, independently reviewable change
that leaves the repository coherent.

1. Select one tiny logical change and state its intended commit purpose.
2. Edit only the files needed for that purpose.
3. Run the most focused relevant test and every configured lint, format, type,
   import, lock, or documentation check that applies.
4. Run `git status --short` and `git diff`.
5. Stage only named files; never use `git add .` or `git add -A`.
6. Run `git diff --staged` and confirm it contains exactly one concern.
7. Commit immediately with a specific Conventional Commit message.
8. Run `git status --short`; it must be empty before the next change.

Keep one concern per commit. Split dependency additions, behaviors, substantial
test groups, refactors, and independent documentation topics. A behavior and a
small inseparable test may share a commit when separating them would leave a
broken or misleading state. Never accumulate completed changes for a later bulk
commit.

Do not squash, amend, reorder, rebase, or otherwise rewrite commits unless the
user explicitly requests it. Do not create WIP, empty, placeholder, or knowingly
failing commits. Do not make unrelated "while here" edits. Preserve user changes
and stop if they overlap the current change in a way that cannot be isolated.

Use these commit prefixes: `feat:`, `fix:`, `test:`, `docs:`, `chore:`, and
`refactor:`. Add a body when the reason or tradeoff is not obvious.

After each commit, report its short hash and message, purpose, changed files,
validation evidence, and clean-tree status. Before starting the next change,
state its exact intended purpose.

## Testing expectations

- Add focused tests with every behavior change unless the commit has no testable
  behavior.
- Keep unit tests close to deterministic domain behavior and node-level tests
  focused on one graph stage.
- Test error paths at every I/O boundary when that boundary is introduced.
- Add a small number of high-value graph integration scenarios rather than a
  broad shallow end-to-end suite.
- Mock OCR engines, LLM clients, remote storage, and other external services.
  Tests must not require credentials, network access, or installed service
  binaries.
- Use only deterministic synthetic or appropriately licensed fixtures. Never
  copy real invoice or customer data into tests.
- Run the full suite after dependency, cross-cutting, or graph integration
  changes and before completing a phase.

For documentation-only changes, verify every referenced path and command and run
the focused health test when the documented development workflow is affected.

## Documentation expectations

`README.md` is the concise user and contributor entry point. The Phase 0
documentation set is:

- `docs/architecture.md` for current boundaries and the explicitly planned flow;
- `docs/development.md` for setup, commands, configuration, and workflow;
- `docs/testing.md` for tests, fixtures, mocks, and required evidence;
- `docs/data-and-security.md` for data, secret, logging, upload, and retention
  rules;
- `docs/api.md` for implemented endpoints and limitations; and
- `docs/decisions/README.md` for ADR conventions and the decision index.

Do not claim that planned endpoints or later-phase capabilities already exist.

Update documentation with the related feature or in the immediately following
focused documentation commit. Link between documents instead of copying large
sections. Use `docs/decisions/` for meaningful architecture decisions with
title, status, context, decision, alternatives, and consequences; do not create
ADRs for trivial choices.

Update this guide when commands, package boundaries, test conventions, required
checks, phase status, or architectural decisions change. A workflow change must
update this file in the same commit when inseparable or in the immediately
following documentation commit.

## Security and data rules

- Never commit real invoices, production documents, personal information,
  customer data, credentials, or confidential business data.
- Commit only synthetic, fictional, programmatically generated, or appropriately
  licensed public fixtures.
- Never commit `.env`; keep only safe placeholders in `.env.example`.
- Read configuration from the environment and validate required values at
  startup when configuration is introduced.
- Do not log document bodies, secrets, credentials, or sensitive extracted
  fields. Use correlation identifiers and stage names for operational context.
- Validate content type, signature, size, page/pixel bounds, and filenames before
  expensive parsing when uploads are approved.
- Bound streaming reads, isolate temporary files, clean them up deterministically,
  and document retention behavior before accepting documents.
- Public errors must not expose internal paths, stack traces, secrets, or raw
  document content.

## Phase boundaries

- Phase 0: repository hygiene, `uv` scaffold, FastAPI application, typed health
  endpoint, focused tests, and accurate initial documentation. **Complete.**
- Phase 1: safe ingestion and one documented OCR baseline. Requires approval.
- Phase 2: typed invoice extraction and LangGraph state/node. Requires approval.
- Phase 3: SQLite repository and deterministic/statistical verification. Requires
  approval.
- Phase 4: evidence-grounded explanation with deterministic fallback. Requires
  approval.
- Phase 5: complete processing API and minimal review interface. Requires approval.
- Phase 6: final integration, documentation, and operational pass. Requires
  approval.

Stop after the currently approved phase. Before every later phase, inspect the
repository, run the existing suite, present the implementation and commit plan,
identify documentation changes, and wait for explicit approval.
