# Release Evidence

## Phase 7 completion snapshot

The local Phase 7 completion gate was recorded on 2026-08-02 against commit
`d87d2fa` before this evidence file was added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 116 files already formatted |
| `uv run --no-sync mypy` | No issues in 50 production source files |
| `uv run --no-sync pytest --cov=veridoc` | 117 passed; 93.35% branch coverage against a 90% floor |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content and path-safety validation |
| Isolated-wheel import | Imported `veridoc` and created the FastAPI application |
| Application smoke | Imported the application and found the `/health` route |
| `git diff --check` | Passed |

`pip-audit` skipped only the unpublished local `veridoc` package because it is
not present on PyPI; all resolved third-party dependencies remained in scope.
During locked synchronization, uv repaired a stale local `websockets`
installation whose distribution metadata lacked a `RECORD` file. The command
completed successfully and the later audit, test, build, and isolated-wheel
checks all passed.

## Phase 8 completion snapshot

The local Phase 8 completion gate was recorded on 2026-08-03 against commit
`69e2e3c` before this evidence section and the final phase-status updates were
added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 138 files already formatted |
| `uv run --no-sync mypy` | No issues in 58 production source files |
| `uv run --no-sync pytest --cov=veridoc` | 178 passed; 93.39% branch coverage against a 90% floor |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Cache-free isolated-wheel import | Imported the built wheel, both console scripts, FastAPI app, and administration routes |
| Application and CLI smoke | Loaded `/health`, the admin Bearer schema, and `veridoc-reference --help` |
| Local Markdown links | All links resolved across 19 tracked Markdown files |
| `git diff --check` and `git status --short` | Passed with a clean worktree |

`pip-audit` again skipped only the unpublished local `veridoc` package. Locked
synchronization repeated the pre-existing stale `websockets` metadata repair
warning but completed successfully. The first local isolated-wheel attempt
demonstrated that uv could reuse a prior same-version wheel from its cache; the
CI and documented smoke command now use `--no-cache`, and the cache-free rerun
verified the current Phase 8 artifact.

## Post-Phase 8 hardening snapshot

The local administration-hardening gate was recorded on 2026-08-04 against
commit `b959497` before this evidence section was added. Phase 9 was not started.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 138 files already formatted |
| `uv run --no-sync mypy` | No issues in 58 production source files |
| `uv run --no-sync pytest --cov=veridoc` | 182 passed; 93.46% branch coverage against a 90% floor |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Cache-free isolated-wheel import | Imported the built wheel, both console scripts, FastAPI app, `/health`, and administration routes |
| Application and CLI smoke | Loaded the admin Bearer schema and `veridoc-reference --help` |
| Local Markdown links | All links resolved across 19 tracked Markdown files |
| `git diff --check` and `git status --short` | Passed with a clean worktree |

`pip-audit` skipped only the unpublished local `veridoc` package. Locked
synchronization repeated the pre-existing stale `websockets` metadata repair
warning but completed successfully; every later local gate passed.

## 2026-08-11 Phase 0-8 hardening snapshot

The local Phase 0-8 hardening gate was recorded on 2026-08-11 against commit
`118e7e4` before this evidence section was added. Phase 9 was not started.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 141 files already formatted |
| `uv run --no-sync mypy` | No issues in 59 production source files |
| `uv run --no-sync pytest --cov=veridoc` | 223 passed; 94.28% branch coverage against a 90% floor |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content, entry-point, schema-module, and path-safety validation |
| Cache-free isolated-wheel smoke | Verified version metadata, console scripts, documented API routes, and the runtime review route |
| Maintenance CLI smoke | Loaded `veridoc-reference --help` |
| Local Markdown links | All 50 local links resolved across 19 tracked Markdown files |
| Full-tree and working-tree whitespace checks | Passed |
| `git status --short` | Passed with a clean worktree |

`pip-audit` skipped only the unpublished local `veridoc` package. Locked
synchronization repeated the pre-existing stale `websockets` metadata repair
warning and used a cross-filesystem copy fallback; synchronization completed
successfully and every later local gate passed.

## 2026-08-12 Phase 0-8 hardening snapshot

The local Phase 0-8 hardening gate was recorded on 2026-08-12 against commit
`7cd5d31` before this evidence section was added. Phase 9 was not started.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 142 files already formatted |
| `uv run --no-sync mypy` | No issues in 59 production source files |
| `uv run --no-sync pytest --cov=veridoc --cov-report=term-missing` | 278 passed; 95.41% branch coverage against a 90% floor |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content, entry-point, schema-module, and path-safety validation |
| Cache-free isolated-wheel smoke | The wheel passed `scripts/smoke_distribution.py` |
| Cache-free isolated-source-distribution smoke | The source distribution built, installed, and passed the same smoke script |
| Local Markdown links | No broken local links across 20 Markdown files |
| Test-module inventory | `docs/testing.md` lists every `tests/test_*.py` module |
| Full-tree and working-tree whitespace checks | Passed |
| `git status --short` | Passed with a clean worktree |

`pip-audit` skipped only the unpublished local `veridoc` package. Locked
synchronization repaired the pre-existing stale `websockets` metadata and used
a cross-filesystem copy fallback; synchronization completed successfully and
every later local gate passed. The isolated source-distribution resolver emitted
informational warnings while ignoring obsolete upstream package files, then
completed the build, installation, and smoke check successfully.

## 2026-08-13 Phase 0-8 hardening snapshot

The local Phase 0-8 hardening gate was recorded on 2026-08-13 against commit
`799ac4c` before this evidence section was added. Phase 9 was not started.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 142 files already formatted |
| `uv run --no-sync mypy` | No issues in 59 production source files |
| `uv run --no-sync pytest --cov=veridoc` | 284 passed; 95.48% branch coverage against a 90% floor |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content, entry-point, schema-module, and path-safety validation |
| Cache-free isolated-wheel smoke | The wheel passed `scripts/smoke_distribution.py` |
| Cache-free isolated-source-distribution smoke | The source distribution built, installed, and passed the same smoke script |
| Local Markdown links | No broken local links across 19 tracked Markdown files |
| Test-module inventory | All 59 `tests/test_*.py` modules are listed in `docs/testing.md` |
| Full-tree and working-tree whitespace checks | Passed |
| `git status --short` | Passed with a clean worktree |

`pip-audit` skipped only the unpublished local `veridoc` package. The isolated
source-distribution resolver emitted informational warnings while ignoring
obsolete upstream package files, then completed the build, installation, and
smoke check successfully.

## 2026-08-13 Provider hardening snapshot

The local Phase 0-8 hardening gate was rerun on 2026-08-13 against commit
`998ee3f` before this evidence section was added. Phase 9 was not started.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 142 files already formatted |
| `uv run --no-sync mypy` | No issues in 59 production source files |
| `uv run --no-sync pytest --cov=veridoc` | 286 passed; 95.49% branch coverage against a 90% floor |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content, entry-point, schema-module, and path-safety validation |
| Cache-free isolated-wheel smoke | The wheel passed `scripts/smoke_distribution.py` |
| Cache-free isolated-source-distribution smoke | The source distribution built, installed, and passed the same smoke script |
| Local Markdown links | No broken local links across 19 tracked Markdown files |
| Test-module inventory | All 59 `tests/test_*.py` modules are listed in `docs/testing.md` |
| Full-tree and working-tree whitespace checks | Passed |
| `git status --short` | Passed with a clean worktree |

`pip-audit` skipped only the unpublished local `veridoc` package. The isolated
source-distribution resolver emitted informational warnings while ignoring
obsolete upstream package files, then completed the build, installation, and
smoke check successfully.

## 2026-08-13 Planning and hardening snapshot

The local Phase 0-8 gate was rerun on 2026-08-13 against commit `21e103f`
before this evidence section was added. Candidate Phases 9 through 11 now have
detailed approval-gated plans, but remain unapproved and unimplemented; no
Phase 9 runtime work was started.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 143 files already formatted |
| `uv run --no-sync mypy` | No issues in 59 production source files |
| `uv run --no-sync pytest --cov=veridoc` | 292 passed; 95.50% branch coverage against a 90% floor |
| `uv run --no-sync pytest tests/test_documentation.py` | Local Markdown links resolved and all 60 test modules matched the testing guide |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content, entry-point, schema-module, and path-safety validation |
| Cache-free isolated-wheel smoke | The wheel passed `scripts/smoke_distribution.py` |
| Cache-free isolated-source-distribution smoke | The source distribution built, installed, and passed the same smoke script |
| Maintenance CLI smoke | Loaded `veridoc-reference --help` |
| Full tracked-tree and working-tree whitespace checks | Passed |
| `git status --short` | Passed with a clean worktree |

`pip-audit` skipped only the unpublished local `veridoc` package. Locked
synchronization repeated the pre-existing stale `websockets` metadata repair
and cross-filesystem copy warnings but completed successfully. The isolated
artifact resolver emitted informational warnings while ignoring obsolete
upstream package files, then completed both installs and smoke checks.

## 2026-08-14 Toolchain reproducibility snapshot

The local Phase 0-8 gate was rerun on 2026-08-14 against commit `d39bf95`
before this evidence section was added. Candidate Phases 9 through 11 remain
unapproved and unimplemented; no Phase 9 runtime work was started.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 143 files already formatted |
| `uv run --no-sync mypy` | No issues in 59 production source files |
| `uv run --no-sync pytest --cov=veridoc` | 292 passed; 95.50% branch coverage against a 90% floor |
| `uv run --no-sync pytest tests/test_documentation.py` | Local Markdown links resolved and all 60 test modules matched the testing guide |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content, entry-point, schema-module, and path-safety validation |
| Cache-free isolated-wheel smoke | The wheel passed `scripts/smoke_distribution.py` |
| Cache-free isolated-source-distribution smoke | The source distribution built, installed, and passed the same smoke script |
| Maintenance CLI smoke | Loaded `veridoc-reference --help` |
| Full tracked-tree and working-tree whitespace checks | Passed |
| `git status --short` | Passed with a clean worktree |

`pip-audit` skipped only the unpublished local `veridoc` package. Locked
synchronization repeated the pre-existing stale `websockets` metadata repair
and cross-filesystem copy warnings; the isolated artifact resolver emitted
informational warnings while ignoring obsolete upstream package files. All
commands completed successfully.

## 2026-08-15 Boundary hardening snapshot

The local Phase 0-8 gate was rerun on 2026-08-15 against commit `e515321`
before this evidence section was added. Candidate Phases 9 through 11 remain
unapproved and unimplemented; no Phase 9 runtime work was started.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 143 files already formatted |
| `uv run --no-sync mypy` | No issues in 59 production source files |
| `uv run pytest --cov=veridoc` | 351 passed; 95.96% branch coverage against a 90% floor |
| `uv run --no-sync pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content, entry-point, schema-module, and path-safety validation |
| Cache-free isolated-wheel smoke | The wheel passed `scripts/smoke_distribution.py` |
| Cache-free isolated-source-distribution smoke | The source distribution built, installed, and passed the same smoke script |
| Maintenance CLI smoke | Loaded `veridoc-reference --help` |
| Full tracked-tree and working-tree whitespace checks | Passed |
| Merge-conflict marker scan | Passed |
| `git status --short` | Passed with a clean worktree |

`pip-audit` skipped only the unpublished local `veridoc` package. Locked
synchronization repeated the stale `websockets` metadata repair and
cross-filesystem copy warnings, but it completed successfully and every later
local gate passed. The isolated artifact resolver emitted informational warnings
while ignoring obsolete upstream package files, then completed both installs and
smoke checks.

## 2026-08-16 Phase 9 planning snapshot

The local Phase 0-8 gate was rerun on 2026-08-16 against commit `c952325`
before this evidence section was added. The run validates the current
implementation and the approval-ready Phase 9 plan; Phase 9 through Phase 11
remain unapproved and unimplemented.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 144 files already formatted |
| `uv run --no-sync mypy` | No issues in 59 production source files |
| `uv run --no-sync pytest --cov=veridoc` | 351 passed; 95.96% branch coverage against a 90% floor |
| `uv run --no-sync pytest tests/test_documentation.py tests/test_health.py` | Documentation inventory, local links, and health contract passed |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content, entry-point, schema-module, and path-safety validation |
| Cache-free isolated-wheel smoke | The wheel passed `scripts/smoke_distribution.py` |
| Cache-free isolated-source-distribution smoke | The source distribution built, installed, and passed the same smoke script |
| Maintenance CLI smoke | Loaded `veridoc-reference --help` |
| Working-tree whitespace and merge-conflict scans | Passed |
| `git status --short` | Passed with a clean worktree |

`pip-audit` skipped only the unpublished local `veridoc` package. Locked
synchronization repaired the stale local `websockets` metadata and used the
cross-filesystem copy fallback; every later local gate passed. The isolated
artifact resolver emitted informational warnings while ignoring obsolete
upstream package files, then completed both installs and smoke checks. No hosted
CI run, provider call, Phase 9 runtime behavior, or deployment evidence was
observed.

## Phase 9 completion snapshot

The local Phase 9 completion gate was recorded on 2026-08-23 against commit
`ac75ce2`, immediately after every item in the
[Phase 9 approval and implementation plan](phase-9-plan.md) was implemented,
tested, and documented. Phase 10 and Phase 11 were not started.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 187 files already formatted |
| `uv run --no-sync mypy` | No issues in 74 production source files |
| `uv run --no-sync pytest --cov=veridoc` | 781 passed; 95.31% branch coverage against a 90% floor |
| `uv run --no-sync pytest tests/test_documentation.py` | Local Markdown links across 23 tracked files and the documented inventory of all 85 test modules passed |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation, including the Phase 9 review router, console page, and persistence/maintenance modules |
| Cache-free isolated-wheel smoke | The wheel passed `scripts/smoke_distribution.py`, including every Phase 9 review route family and the `/review/console` page |
| Cache-free isolated-source-distribution smoke | The source distribution built, installed, and passed the same smoke script |
| Maintenance CLI smoke | Loaded `veridoc-reference --help` and `veridoc-review --help` |
| Full tracked-tree whitespace and merge-conflict scans | Passed |
| `git status --short` | Passed with a clean worktree |

`pip-audit` skipped only the unpublished local `veridoc` package. Locked
synchronization repeated the pre-existing stale local `websockets` metadata
repair; every later local gate passed. The isolated wheel smoke initially
failed before this phase's `scripts/smoke_distribution.py` fix (see the
CHANGELOG): `app.include_router(...)` does not always flatten sub-routes
directly into `app.routes` — on this environment's resolved Starlette
version, an included router appears as an opaque wrapper exposing its
routes only through `original_router.routes`, which made every review API
route invisible to the prior naive `app.routes` scan. The fixed,
recursive route-discovery logic is what the passing result above reflects.

This snapshot exercises the review workflow only through deterministic
in-process fakes and the ASGI transport, exactly like every other route
family in this repository: no real browser, no HTTPS-terminating reverse
proxy, no OpenAI credential, and no installed Tesseract executable were
used. It does not claim a remote CI pass, a verified real-browser session
against a `Secure` cookie over actual HTTPS, deployment readiness, or
production identity-provider integration — those remain Phase 10 concerns.
The local actor file, session model, and CSRF protection are exactly what
[ADR 0008](decisions/0008-use-local-actor-file-and-http-only-sessions-for-review.md)
scoped them to be: an operator-managed local control, not a production
identity system.

## Post-Phase 9 hardening snapshot

The local Phase 0-9 gate was rerun on 2026-09-04 against commit
`a56dff4` before this evidence section was added. Phase 10 and Phase 11
were not started.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 187 files already formatted |
| `uv run --no-sync mypy` | No issues in 74 production source files |
| `uv run --no-sync pytest --cov=veridoc` | 843 passed; 95.42% branch coverage against a 90% floor |
| `uv run --no-sync pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Cache-free isolated-wheel smoke | The wheel passed `scripts/smoke_distribution.py` |
| Cache-free isolated-source-distribution smoke | The source distribution built, installed, and passed the same smoke script |
| Maintenance CLI smoke | Loaded `veridoc-reference --help` and `veridoc-review --help` |
| Working-tree whitespace and merge-conflict scans | Passed |
| `git status --short` | Passed with a clean worktree |

`pip-audit` skipped only the unpublished local `veridoc` package. No hosted
CI run, provider call, Phase 10 runtime behavior, or deployment evidence was
observed.

## Phase 10 completion snapshot

The local Phase 10 completion gate was recorded on 2026-09-17 against commit
`4610c72` before this evidence section was added. Phase 11 was not started.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 221 files already formatted |
| `uv run --no-sync mypy` | No issues in 89 production source files |
| `uv run --no-sync pytest --cov=veridoc` | 962 passed; 95.03% branch coverage against a 90% floor |
| `uv run --no-sync pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Cache-free isolated-wheel smoke | The wheel passed `scripts/smoke_distribution.py` |
| Cache-free isolated-source-distribution smoke | The source distribution built, installed, and passed the same smoke script |
| Maintenance CLI smoke | Loaded `veridoc-reference --help`, `veridoc-review --help`, `veridoc-quarantine --help`, and `veridoc-backup --help` |
| Working-tree whitespace and merge-conflict scans | Passed |
| `git status --short` | Passed with a clean worktree |

`pip-audit` skipped only the unpublished local `veridoc` package. The Phase 10
deliverables (container packaging, runtime secret entrypoint, readiness probe,
loopback admin restriction, deployment rate/concurrency limits, pre-decode upload
quarantine, automated backup retention, operational telemetry registry, and operations
runbook) are fully verified and documented. No hosted CI run, live cloud provider call,
or Phase 11 corpus evaluation was executed.

## Phase 11 completion snapshot

The local Phase 11 completion gate was recorded on 2026-09-17 against commit
`f5e477c` before this evidence section was added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run --no-sync pip-audit` | No known third-party vulnerabilities |
| `uv run --no-sync ruff check .` | Passed |
| `uv run --no-sync ruff format --check .` | 247 files already formatted |
| `uv run --no-sync mypy` | No issues in 101 production source files |
| `uv run --no-sync pytest --cov=veridoc` | 1001 passed; 94.42% branch coverage against a 90% floor |
| `uv run --no-sync pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run --no-sync twine check dist/*` | Both distributions passed metadata validation |
| `uv run --no-sync python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Cache-free isolated-wheel smoke | The wheel passed `scripts/smoke_distribution.py` |
| Cache-free isolated-source-distribution smoke | The source distribution built, installed, and passed the same smoke script |
| Maintenance CLI smoke | Loaded `veridoc-reference --help`, `veridoc-review --help`, `veridoc-quarantine --help`, `veridoc-backup --help`, and `veridoc-evaluate --help` |
| Evaluation benchmark run | `veridoc-evaluate` verified offline synthetic corpus benchmark in `tests/fixtures/corpus` |
| Working-tree whitespace and merge-conflict scans | Passed |
| `git status --short` | Passed with a clean worktree |

`pip-audit` skipped only the unpublished local `veridoc` package. The Phase 11
deliverables (preregistered evaluation protocol, synthetic corpus governance,
OCR CER/WER metrics, extraction exact-match/F1/grounding metrics, verification
confusion and verdict concordance metrics, explanation guardrail metrics,
artifact and provider drift detection, deterministic runner with Wilson score
confidence intervals, threshold-driven decision evaluation, `veridoc-evaluate`
CLI, and baseline benchmark evaluation report) are fully verified and documented.

## Phase 12 completion snapshot

The local Phase 12 completion gate was recorded on 2026-09-19 against commit
`7aab1b9` before this evidence section was added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | No known third-party vulnerabilities |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | 261 files already formatted |
| `uv run mypy` | No issues in 106 production source files |
| `uv run pytest --cov=veridoc` | 1046 passed; 94.12% branch coverage against a 90% floor |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Distribution smoke | Passed `scripts/smoke_distribution.py` including vendor schema routes |
| Maintenance CLI smoke | Loaded `veridoc-reference --help` (including `vendors` command), `veridoc-review --help`, `veridoc-quarantine --help`, `veridoc-backup --help`, and `veridoc-evaluate --help` |
| Working-tree whitespace and merge-conflict scans | Passed |
| `git status --short` | Passed with a clean worktree |

`pip-audit` skipped only the unpublished local `veridoc` package. The Phase 12
deliverables (authoritative vendor master entity schemas, SQLite Migration 5,
`VendorRepository` protocol and SQLite implementation, deterministic multi-attribute
cascading entity resolution engine, deterministic remit-to bank account mismatch
and tax ID verification rules, `vendor_resolution` in `ProcessingResult`, loopback-isolated
Bearer-authenticated vendor administration routes, `veridoc-reference vendors` CLI
commands, and review console vendor resolution badges and bank account mismatch warning
indicators) are fully verified and documented.

## Phase 13 completion snapshot

The local Phase 13 completion gate was recorded on 2026-09-22 against the
expanded benchmark corpus commit before this evidence section was added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | No known third-party vulnerabilities (local `veridoc` skipped as unpublished) |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | All files already formatted |
| `uv run mypy` | No issues in 106 production source files |
| `uv run pytest --cov=veridoc` | 1056 passed; 94.11% branch coverage against a 90% floor |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Distribution smoke | Passed `scripts/smoke_distribution.py` for the isolated wheel and source distribution |
| Maintenance CLI smoke | Loaded `veridoc-reference --help`, `veridoc-review --help`, `veridoc-quarantine --help`, `veridoc-backup --help`, and `veridoc-evaluate --help` |
| Corpus manifest integrity | `load_corpus_manifest` verifies all 20 documents and ground truths; every language, quality, layout, and page-count slice holds exactly 10 samples |
| Fake-harness benchmark | `veridoc-evaluate` exits 0 over the expanded corpus with every slice marked sufficient; observed metric values are test-double artifacts, not product measurements |
| Working-tree whitespace and merge-conflict scans | Passed |
| `git status --short` | Passed with a clean worktree |

The Phase 13 deliverables (ADR 0024, page-count slice bucketing, 17 new
synthetic documents with complete ground truth, the
`veridoc-synthetic-benchmark-v2` manifest, corpus validity tests, the
committed construction script, fixture-guide corpus rules, the runbook
measured re-run procedure, and corrected `veridoc-evaluate` CLI
documentation) are fully verified and documented. The Tesseract-measured
re-run that updates the readiness decision remains an explicit operator
step for the equipped environment and is recorded as the recommended
Phase 14.

## Phase 15 completion snapshot

The local Phase 15 completion gate was recorded on 2026-09-23 against the
evidence-export implementation before this evidence section was added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | No known third-party vulnerabilities (local `veridoc` skipped as unpublished) |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | All files already formatted |
| `uv run mypy` | No issues in 107 production source files |
| `uv run pytest --cov=veridoc` | 1081 passed; 93.96% branch coverage against a 90% floor |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Distribution smoke | Passed `scripts/smoke_distribution.py` for the isolated wheel and source distribution, including the evidence route |
| Maintenance CLI smoke | Loaded `veridoc-reference --help`, `veridoc-review --help` (including `export` and `verify-bundle`), `veridoc-quarantine --help`, `veridoc-backup --help`, and `veridoc-evaluate --help` |
| Working-tree whitespace and merge-conflict scans | Passed |
| `git status --short` | Passed with a clean worktree |

The Phase 15 deliverables (ADR 0025, the `veridoc.review.evidence`
build/verify domain module, the authenticated evidence export route, the
`export` and `verify-bundle` review commands, the console download control,
tamper-evident and route/CLI/markup coverage, and synchronized API,
architecture, runbook, testing, changelog, README, and operating guidance)
are fully verified and documented. Phase 14 remains planned but blocked on
a Tesseract-equipped operator environment; nothing in Phase 15 changes its
entry criteria or runbook procedure.

## Phase 16 completion snapshot

The local Phase 16 completion gate was recorded on 2026-09-24 against the
reconciliation-precision implementation before this evidence section was
added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | No known third-party vulnerabilities (local `veridoc` skipped as unpublished) |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | All files already formatted |
| `uv run mypy` | No issues in 107 production source files |
| `uv run pytest --cov=veridoc` | 1092 passed; 93.92% branch coverage against a 90% floor |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Distribution smoke | Passed `scripts/smoke_distribution.py` for the isolated wheel and source distribution |
| Maintenance CLI smoke | Loaded `veridoc-reference --help`, `veridoc-review --help`, `veridoc-quarantine --help`, `veridoc-backup --help`, and `veridoc-evaluate --help` |
| Working-tree whitespace and merge-conflict scans | Passed |
| `git status --short` | Passed with a clean worktree |

The Phase 16 deliverables (ADR 0026, canonical invoice-number
normalization, normalized duplicate detection over one shared history
load, one-sided PO total/quantity ceilings, the cumulative split-billing
ceiling, updated PO/duplicate/service tests, and synchronized architecture,
changelog, roadmap, and operating guidance) are fully verified and
documented. No schema, migration, finding-type, threshold, or endpoint
changes. Phase 14 remains planned but blocked on a Tesseract-equipped
operator environment.

## Phase 17 completion snapshot

The local Phase 17 completion gate was recorded on 2026-09-24 against the
audit-trail implementation before this evidence section was added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | No known third-party vulnerabilities (local `veridoc` skipped as unpublished) |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | All files already formatted |
| `uv run mypy` | No issues in 107 production source files |
| `uv run pytest --cov=veridoc` | 1108 passed; 94.11% branch coverage against a 90% floor |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Distribution smoke | Passed `scripts/smoke_distribution.py` for the isolated wheel and source distribution |
| Maintenance CLI smoke | Loaded `veridoc-reference --help` (including `audit-log`), `veridoc-review --help`, `veridoc-quarantine --help`, `veridoc-backup --help`, and `veridoc-evaluate --help` |
| Working-tree whitespace and merge-conflict scans | Passed |
| `git status --short` | Passed with a clean worktree |

The Phase 17 deliverables (ADR 0027, forward-only migration 6, schema and
maintenance validation for the audit table, bounded audit models and
protocol operations, in-transaction audit writes on every invoice,
purchase-order, and vendor create/update/delete/import, request-ID
linkage, the `veridoc-reference audit-log` command, migration,
round-trip, linkage, malformed-row, backup/restore, and CLI tests, and
synchronized architecture, API, data-and-security, changelog, roadmap,
and operating guidance) are fully verified and documented. No finding-type,
threshold, endpoint, or console changes. Phase 14 remains planned but
blocked on a Tesseract-equipped operator environment.

## Phase 18 completion snapshot

The local Phase 18 completion gate was recorded on 2026-09-24 against the
operator-surface implementation before this evidence section was added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | No known third-party vulnerabilities (local `veridoc` skipped as unpublished) |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | All files already formatted |
| `uv run mypy` | No issues in 107 production source files |
| `uv run pytest --cov=veridoc` | 1111 passed; 94.05% branch coverage against a 90% floor |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Distribution smoke | Passed `scripts/smoke_distribution.py` for the isolated wheel and source distribution |
| Maintenance CLI smoke | Loaded `veridoc-reference --help` (including `vendors add/update` and `audit-log`), `veridoc-review --help`, `veridoc-quarantine --help`, `veridoc-backup --help`, and `veridoc-evaluate --help` |
| Working-tree whitespace and merge-conflict scans | Passed |
| `git status --short` | Passed with a clean worktree |

The Phase 18 deliverables (vendor add/update commands with bounded JSON
input, audit entries for the previously unaudited CLI delete path,
console previous/next pagination, CLI contract tests, console markup
tests, and corrected vendor CLI documentation) are fully verified and
documented. No API, schema, migration, finding-type, or threshold
changes. Phase 14 remains planned but blocked on a Tesseract-equipped
operator environment.

## Phase 19 completion snapshot

The local Phase 19 completion gate was recorded on 2026-09-25 against the
CLI record implementation before this evidence section was added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | No known third-party vulnerabilities (local `veridoc` skipped as unpublished) |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | All files already formatted |
| `uv run mypy` | No issues in 107 production source files |
| `uv run pytest --cov=veridoc` | 1115 passed; 93.86% branch coverage against a 90% floor |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Distribution smoke | Passed `scripts/smoke_distribution.py` for the isolated wheel and source distribution |
| Maintenance CLI smoke | Loaded `veridoc-reference --help` (including `invoices`, `purchase-orders`, `vendors`, and `audit-log`), `veridoc-review --help`, `veridoc-quarantine --help`, `veridoc-backup --help`, and `veridoc-evaluate --help` |
| Working-tree whitespace and merge-conflict scans | Passed |
| `git status --short` | Passed with a clean worktree |

The Phase 19 deliverables (invoice and purchase-order add/update/delete
commands with bounded JSON reads, schema validation, conflict reporting,
and per-command audit entries; CLI contract tests proving audit linkage;
and synchronized development-guide, changelog, README, and operating
guidance) are fully verified and documented. No API, schema, migration,
finding-type, or threshold changes. Phase 14 remains planned but blocked
on a Tesseract-equipped operator environment.

## Phase 20 completion snapshot

The local Phase 20 completion gate was recorded on 2026-09-27 against the
review inspection and session lifecycle implementation before this evidence section was added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13, required by `pyproject.toml`; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv sync --all-groups --locked` | Completed from the committed lockfile |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | No known third-party vulnerabilities (local `veridoc` skipped as unpublished) |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | All files already formatted |
| `uv run mypy src/veridoc` | No issues in 107 production source files |
| `uv run pytest --cov=veridoc` | 1133 passed; 93.61% branch coverage against a 90% floor |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built one wheel and one source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Distribution smoke | Passed `scripts/smoke_distribution.py` for the isolated wheel and source distribution |
| Maintenance CLI smoke | Loaded `veridoc-reference --help`, `veridoc-review --help` (including `cases` and `sessions`), `veridoc-backup --help` (with `--session-retention-days`), `veridoc-quarantine --help`, and `veridoc-evaluate --help` |
| Working-tree whitespace and merge-conflict scans | Passed |
| `git status --short` | Passed with a clean worktree |

The Phase 20 deliverables (review session summary models, session store
protocol methods, SQLite session queries/revocation/pruning, `veridoc-review
cases list|get` inspection commands, `veridoc-review sessions
list|revoke|prune` lifecycle management, automated deployment session pruning
in `veridoc-backup --session-retention-days`, and DOM-safe review console
case filtering by status and assignee) are fully verified and documented. No
API, schema, migration, finding-type, or threshold changes. Phase 14 remains
planned but blocked on a Tesseract-equipped operator environment.

## Phase 21 completion snapshot

The local Phase 21 completion gate was recorded on 2026-09-30 against commit
`0d43f18` before this evidence section and the final documentation updates were
added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | 275 files already formatted |
| `uv run mypy` | No issues in 108 production source files |
| `uv run pytest --cov=veridoc` | 1154 passed; 93.63% branch coverage against a 90% floor |
| `uv run pytest tests/test_verification_staleness.py` | 21 passed |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `git status --short` | Clean worktree |

The Phase 21 deliverables (`stale_invoice` finding type, `check_invoice_staleness`
pure function with injected reference date, `VerificationService` integration,
21 staleness tests, ADR 0028, updated testing.md inventory, updated AGENTS.md,
updated roadmap, and updated CHANGELOG) are fully verified and documented. No
API, schema migration, new dependency, route, or threshold change was made.
Phase 14 remains planned but blocked on a Tesseract-equipped operator
environment.

## Phase 22 completion snapshot

The local Phase 22 completion gate was recorded on 2026-10-04 against commit
`cf7e952` before this evidence section was added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | 278 files already formatted |
| `uv run mypy` | No issues in 109 production source files |
| `uv run pytest --cov=veridoc` | 1173 passed; 93.65% branch coverage against a 90% floor |
| `uv run pytest tests/test_verification_future_dates.py` | 19 passed |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built wheel and source distribution |
| `uv run twine check dist/*` | PASSED |
| `uv run python scripts/check_distribution.py` | Validated wheel and source distribution |
| Isolated wheel smoke test | PASSED |
| Isolated source-distribution smoke test | PASSED |
| `git diff --check` | Clean (zero whitespace errors) |
| `git status --short` | Clean worktree |

The Phase 22 deliverables (`future_invoice_date` finding type, `check_future_invoice_date`
pure function with injected reference date, `VerificationService` integration,
19 future invoice date tests, ADR 0029, updated testing.md inventory, updated AGENTS.md,
updated roadmap, and updated CHANGELOG) are fully verified and documented. No
API, schema migration, new dependency, route, or threshold change was made.
Phase 14 remains planned but blocked on a Tesseract-equipped operator
environment.

## Phase 23 completion snapshot

The local Phase 23 completion gate was recorded on 2026-10-05 against commit
`522f7eb` before this evidence section was added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | 281 files already formatted |
| `uv run mypy` | No issues in 110 production source files |
| `uv run pytest` | 1195 passed |
| `uv run pytest tests/test_verification_duplicate_line_items.py` | 21 passed |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `git diff --check` | Clean (zero whitespace errors) |
| `git status --short` | Clean worktree |

The Phase 23 deliverables (`duplicate_line_item` finding type, `check_duplicate_line_items`
pure function, `VerificationService` integration, 21 duplicate line item tests,
ADR 0030, updated testing.md inventory, updated AGENTS.md, updated roadmap, and
updated CHANGELOG) are fully verified and documented. No API, schema migration,
new dependency, route, or threshold change was made. Phase 14 remains planned
but blocked on a Tesseract-equipped operator environment.

## Phase 24 completion snapshot

The local Phase 24 completion gate was recorded on 2026-10-07 against commit
`87bf15d` before this evidence section was added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | 284 files already formatted |
| `uv run mypy` | No issues in 111 production source files |
| `uv run pytest --cov=veridoc` | 1224 passed; 93.70% branch coverage against a 90% floor |
| `uv run pytest tests/test_verification_invoice_totals.py` | 28 passed |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built wheel and source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Isolated-wheel smoke test | Passed `scripts/smoke_distribution.py` |
| Isolated source-distribution smoke test | Passed `scripts/smoke_distribution.py` |
| Maintenance CLI smoke | Loaded `veridoc-reference --help`, `veridoc-review --help`, `veridoc-backup --help`, `veridoc-quarantine --help`, and `veridoc-evaluate --help` |
| `git diff --check` | Clean (zero whitespace errors) |
| `git status --short` | Clean worktree |

The Phase 24 deliverables (`non_positive_invoice_total` finding type, `check_non_positive_invoice_total`
pure function in `veridoc.verification.invoice_totals`, `VerificationService` integration,
28 non-positive total tests, ADR 0031, updated testing.md inventory, updated AGENTS.md,
updated architecture.md, updated roadmap, and updated CHANGELOG) are fully verified and documented.
No API, schema migration, new dependency, route, or threshold change was made.
Phase 14 remains planned but blocked on a Tesseract-equipped operator environment.

## Phase 25 completion snapshot

The local Phase 25 completion gate was recorded on 2026-10-08 against commit
`0d5deec` before this evidence section was added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | 288 files already formatted |
| `uv run mypy` | No issues in 112 production source files |
| `uv run pytest --cov=veridoc` | 1252 passed; 93.76% branch coverage against a 90% floor |
| `uv run pytest tests/test_verification_line_item_amounts.py` | 27 passed |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built wheel and source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Isolated-wheel smoke test | Passed `scripts/smoke_distribution.py` |
| Isolated source-distribution smoke test | Passed `scripts/smoke_distribution.py` |
| Maintenance CLI smoke | Loaded `veridoc-reference --help`, `veridoc-review --help`, `veridoc-backup --help`, `veridoc-quarantine --help`, and `veridoc-evaluate --help` |
| `git diff --check` | Clean (zero whitespace errors) |
| `git status --short` | Clean worktree |

The Phase 25 deliverables (`non_positive_line_item` finding type, `check_non_positive_line_items`
pure function in `veridoc.verification.line_item_amounts`, `VerificationService` integration,
27 non-positive line item tests, ADR 0032, updated testing.md inventory, updated AGENTS.md,
updated architecture.md, updated roadmap, and updated CHANGELOG) are fully verified and documented.
No API, schema migration, new dependency, route, or threshold change was made.
Phase 14 remains planned but blocked on a Tesseract-equipped operator environment.

## Phase 26 completion snapshot

The local Phase 26 completion gate was recorded on 2026-10-13 against commit
`b5160dc` before this evidence section was added.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | 290 files already formatted |
| `uv run mypy` | No issues in 113 production source files |
| `uv run pytest --cov=veridoc` | 1293 passed; branch coverage exceeds 90% floor |
| `uv run pytest tests/test_verification_header_amounts.py` | 41 passed |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built wheel and source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Isolated-wheel smoke test | Passed `scripts/smoke_distribution.py` |
| Isolated source-distribution smoke test | Passed `scripts/smoke_distribution.py` |
| Maintenance CLI smoke | Loaded `veridoc-reference --help`, `veridoc-review --help`, `veridoc-backup --help`, `veridoc-quarantine --help`, and `veridoc-evaluate --help` |
| `git diff --check` | Clean (zero whitespace errors) |
| `git status --short` | Clean worktree |

The Phase 26 deliverables (`non_positive_subtotal`, `negative_tax`, and `invalid_discount`
finding types in `veridoc.verification.models`, `check_non_positive_subtotal`, `check_negative_tax`,
`check_invalid_discount`, and composite `check_header_amounts` pure functions in
`veridoc.verification.header_amounts`, `VerificationService` integration in `veridoc.verification.service`,
41 focused tests in `tests/test_verification_header_amounts.py`, ADR 0033, updated testing.md inventory,
updated AGENTS.md, updated architecture.md, updated roadmap, and updated CHANGELOG) are fully verified
and documented. No API, schema migration, new dependency, route, or threshold change was made.
Phase 14 remains planned but blocked on a Tesseract-equipped operator environment.

## Phase 27 completion snapshot

The local Phase 27 completion gate was verified on 2026-10-14 on branch
`phase/header-arithmetic-tolerances`.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | 290 files already formatted |
| `uv run mypy` | No issues in 113 production source files |
| `uv run pytest --cov=veridoc` | 1315 passed; branch coverage exceeds 90% floor |
| `uv run pytest tests/test_verification_arithmetic.py` | 22 passed |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built wheel and source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Isolated-wheel smoke test | Passed `scripts/smoke_distribution.py` |
| Isolated source-distribution smoke test | Passed `scripts/smoke_distribution.py` |
| Maintenance CLI smoke | Loaded `veridoc-reference --help`, `veridoc-review --help`, `veridoc-backup --help`, `veridoc-quarantine --help`, and `veridoc-evaluate --help` |
| `git diff --check` | Clean (zero whitespace errors) |
| `git status --short` | Clean worktree |

The Phase 27 deliverables (`rounding_discrepancy` finding type in `veridoc.verification.models`,
`DEFAULT_ROUNDING_TOLERANCE = Decimal("0.02")` in `veridoc.verification.arithmetic`,
calibrated `check_invoice_total`, `check_line_item_amounts`, and `check_line_items_subtotal`
distinguishing low-severity rounding discrepancies from high-severity material mismatches,
omitted discount and tax normalization in header arithmetic, exported public functions
`check_invoice_total`, `check_line_item_amounts`, `check_line_items_subtotal`, and `check_invoice_dates`,
22 tests in `tests/test_verification_arithmetic.py`, ADR 0034, updated AGENTS.md, updated
architecture.md, updated roadmap, and updated CHANGELOG) are fully verified and documented.
No database schema migration, new dependency, route, or threshold change was made.
Phase 14 remains planned but blocked on a Tesseract-equipped operator environment.

## Phase 28 completion snapshot

The local Phase 28 completion gate was recorded on 2026-10-15 against commit
`18f0ad1` before this evidence section and progress updates were committed.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | All files formatted |
| `uv run mypy` | No issues found across all source files |
| `uv run pytest --cov=veridoc` | 1335 passed; 93.92% branch coverage against a 90% floor |
| `uv run pytest tests/test_verification_payment_terms.py` | 18 passed |
| `uv run pytest tests/test_documentation.py` | Local Markdown links and the documented test-module inventory passed |
| `uv build --clear` | Built wheel and source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Isolated-wheel smoke test | Passed `scripts/smoke_distribution.py` |
| Isolated source-distribution smoke test | Passed `scripts/smoke_distribution.py` |
| Maintenance CLI smoke | Loaded `veridoc-reference --help`, `veridoc-review --help`, `veridoc-backup --help`, `veridoc-quarantine --help`, and `veridoc-evaluate --help` |
| `git diff --check` | Clean (zero whitespace errors) |
| `git status --short` | Clean worktree |

The Phase 28 deliverables (`payment_terms_due_date_mismatch` finding type in `veridoc.verification.models`,
`parse_payment_terms_days` and `check_payment_terms_due_date` in `veridoc.verification.payment_terms`,
weekend business-day roll normalization, accelerated due date high-severity detection, extended due date
medium-severity detection, `VerificationService.verify()` integration, 18 tests in
`tests/test_verification_payment_terms.py`, ADR 0035, updated AGENTS.md, updated architecture.md, updated
roadmap, and updated CHANGELOG) are fully verified and documented. No database schema migration, new dependency,
route, or threshold change was made.
## Phase 29 completion snapshot

The Phase 29 completion gate was recorded on 2026-10-17 against commit
`c7f44fc`.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13;
- GitHub Actions Ubuntu runner (CI run `38978109737`); and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` | Clean (zero whitespace errors) |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | Passed (0 known vulnerabilities) |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | All files formatted |
| `uv run mypy` | No issues found across all source files |
| `uv run pytest --cov=veridoc` | 1336 passed; 93.92% branch coverage against a 90% floor |
| `uv run pytest tests/test_documentation.py` | Local Markdown links, documented test-module inventory, and tracked whitespace hygiene test passed |
| `uv build --clear` | Built wheel and source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Isolated-wheel smoke test | Passed `scripts/smoke_distribution.py` |
| Isolated source-distribution smoke test | Passed `scripts/smoke_distribution.py` |
| GitHub Actions CI (`ci.yml`) | 100% green on run `38978109737` |
| `git status --short` | Clean worktree |

The Phase 29 deliverables (remediated trailing blank lines in tracked documentation,
pre-commit regression test `test_tracked_files_have_no_whitespace_errors` in `tests/test_documentation.py`,
stabilized `FakeClamd` socket streaming in `tests/test_clamav_scanner.py`, updated AGENTS.md,
README.md, CHANGELOG.md, and verified 100% green GitHub Actions CI run `38978109737`) are fully verified.
Phase 14 remains planned but blocked on a Tesseract-equipped operator environment.

## Phase 30 completion snapshot

The Phase 30 completion gate was recorded on 2026-10-17 against the `phase/excessive-due-date-window` branch.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13;
- GitHub Actions Ubuntu runner; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` | Clean (zero whitespace errors) |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | Passed (0 known vulnerabilities) |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | All files formatted |
| `uv run mypy` | No issues found across all source files |
| `uv run pytest --cov=veridoc` | 1347 passed; branch coverage >= 90% floor |
| `uv run pytest tests/test_documentation.py` | Local Markdown links, documented test-module inventory, and tracked whitespace hygiene test passed |
| `uv build --clear` | Built wheel and source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Isolated-wheel smoke test | Passed `scripts/smoke_distribution.py` |
| Isolated source-distribution smoke test | Passed `scripts/smoke_distribution.py` |
| `git status --short` | Clean worktree |

The Phase 30 deliverables (pure deterministic check `check_excessive_due_date_window()`, constant `MAXIMUM_CREDIT_WINDOW_DAYS = 365`,
`excessive_due_date_window` finding type, medium-severity detection, `VerificationService.verify()` integration,
10 tests in `tests/test_verification_due_date_bounds.py`, ADR 0036, updated AGENTS.md, updated architecture.md,
updated roadmap, updated testing guide, and updated CHANGELOG) are fully verified and documented. No database schema
migration, new dependency, or route change was made.
Phase 14 remains planned but blocked on a Tesseract-equipped operator environment.

## Phase 31 completion snapshot

The Phase 31 completion gate was recorded on 2026-10-18 against the `phase/document-type-verification` branch.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13;
- GitHub Actions Ubuntu runner; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` | Clean (zero whitespace errors) |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | Passed (0 known vulnerabilities) |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | All files formatted |
| `uv run mypy` | No issues found across all source files |
| `uv run pytest --cov=veridoc` | 1355 passed; branch coverage >= 90% floor |
| `uv run pytest tests/test_documentation.py` | Local Markdown links, documented test-module inventory, and tracked whitespace hygiene test passed |
| `uv build --clear` | Built wheel and source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Isolated-wheel smoke test | Passed `scripts/smoke_distribution.py` |
| Isolated source-distribution smoke test | Passed `scripts/smoke_distribution.py` |
| `git status --short` | Clean worktree |

The Phase 31 deliverables (pure deterministic check `check_document_type()`, `unsupported_document_type`
finding type, high-severity non-invoice detection, `VerificationService.verify()` integration,
8 tests in `tests/test_verification_document_type.py`, ADR 0037, updated AGENTS.md, updated architecture.md,
updated roadmap, updated testing guide, and updated CHANGELOG) are fully verified and documented. No database schema
migration, new dependency, or route change was made.
Phase 14 remains planned but blocked on a Tesseract-equipped operator environment.

## Phase 32 completion snapshot

The Phase 32 completion gate was recorded on 2026-10-18 against the `phase/extraction-uncertainty-verification` branch.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13;
- GitHub Actions Ubuntu runner; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` | Clean (zero whitespace errors) |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | Passed (0 known vulnerabilities) |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | All files formatted |
| `uv run mypy` | No issues found across all source files |
| `uv run pytest --cov=veridoc` | 1366 passed; branch coverage >= 90% floor |
| `uv run pytest tests/test_documentation.py` | Local Markdown links, documented test-module inventory, and tracked whitespace hygiene test passed |
| `uv build --clear` | Built wheel and source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Isolated-wheel smoke test | Passed `scripts/smoke_distribution.py` |
| Isolated source-distribution smoke test | Passed `scripts/smoke_distribution.py` |
| `git status --short` | Clean worktree |

The Phase 32 deliverables (pure deterministic check `check_extraction_uncertainties()`, `extraction_uncertainty`
finding type, medium-severity declared uncertainty detection, `VerificationService.verify()` integration,
8 tests in `tests/test_verification_uncertainties.py`, ADR 0038, updated AGENTS.md, updated architecture.md,
updated roadmap, updated testing guide, and updated CHANGELOG) are fully verified and documented. No database schema
migration, new dependency, or route change was made.
Phase 14 remains planned but blocked on a Tesseract-equipped operator environment.

## Phase 33 completion snapshot

The Phase 33 completion gate was recorded on 2026-10-21 against the `phase/required-field-completeness` branch.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13;
- GitHub Actions Ubuntu runner; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` | Clean (zero whitespace errors) |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | Passed after upgrading Pillow to 13.0.0 and certifi to 2026.10.19 (0 known vulnerabilities) |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | All files formatted |
| `uv run mypy` | No issues found across all source files |
| `uv run pytest --cov=veridoc` | 1379 passed; total branch coverage 94.01% (90% floor) |
| `uv run pytest tests/test_documentation.py` | Local Markdown links, documented test-module inventory, and tracked whitespace hygiene test passed |
| `uv build --clear` | Built wheel and source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Isolated-wheel smoke test | Passed `scripts/smoke_distribution.py` |
| Isolated source-distribution smoke test | Passed `scripts/smoke_distribution.py` |
| Remote GitHub Actions CI | Run [39518432117](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/actions/runs/39518432117) succeeded for `13bf33e` |
| `git status --short` | Clean worktree |

The Phase 33 deliverables (ordered `REQUIRED_INVOICE_FIELDS` table, pure
`check_required_fields()`, `missing_required_field` finding type, fixed-severity
per-field evidence, first-position `VerificationService.verify()` integration,
12 tests in `tests/test_verification_completeness.py`, ADR 0039, updated
AGENTS.md, architecture.md, roadmap, testing guide, README, and CHANGELOG) are
fully verified and documented. Existing processing, evaluation, and review
integration fixtures were completed with the newly required fields so their
original assertions remain meaningful. A separate dependency commit upgraded
Pillow and certifi to audited versions because the vulnerability database added
findings against the previously locked versions. No database schema migration,
new route, or new dependency was introduced.

## Phase 34 completion snapshot

The Phase 34 completion gate was recorded on 2026-10-22 against the `phase/line-item-completeness` branch, stacked on `phase/required-field-completeness`.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13;
- GitHub Actions Ubuntu runner; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` | Clean (zero whitespace errors) |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | Passed (0 known vulnerabilities; `veridoc` skipped as not on PyPI) |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | All 310 files formatted |
| `uv run mypy` | No issues found across 119 source files |
| `uv run pytest --cov=veridoc` | 1396 passed; total branch coverage 94.02% (90% floor) |
| `uv run pytest tests/test_documentation.py` | Local Markdown links, documented test-module inventory, and tracked whitespace hygiene test passed |
| `uv build --clear` | Built wheel and source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Isolated-wheel smoke test | Passed `scripts/smoke_distribution.py` |
| Isolated source-distribution smoke test | Passed `scripts/smoke_distribution.py` |
| Remote GitHub Actions CI | Run [39847896182](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/actions/runs/39847896182) succeeded for `a863194` |
| `git status --short` | Clean worktree |

The Phase 34 deliverables (pure `check_line_item_completeness()`,
`incomplete_line_item` finding type, identity and amount requirements with
stable structured details, derived `quantity * unit_price` line totals in
`check_line_items_subtotal()`, service integration, 13 tests in
`tests/test_verification_line_item_completeness.py`, extended arithmetic tests,
ADR 0040, updated AGENTS.md, architecture.md, roadmap, testing guide, README,
and CHANGELOG) are fully verified and documented. No database schema migration,
new dependency, new route, extraction schema change, prompt change, or
evaluation-manifest change was introduced.

## Evidence boundaries

The repository workflow reproduces the dependency, audit, quality, test,
coverage, build, distribution, isolated wheel and source-distribution, and
full-tree whitespace gates on GitHub-hosted Ubuntu runners. The pytest gate also
enforces local Markdown links and the documented test-module inventory. The
maintenance CLI smoke and final clean-worktree check remain local evidence.
The Phase 33 and Phase 34 hosted CI results were observed directly (runs 39518432117 and 39847896182); the
snapshot still does not claim deployment readiness, live provider execution, or
accuracy on a representative invoice corpus. Tests use deterministic fakes for
external OCR and model boundaries.

See the [development guide](development.md) for the reproducible commands and
the [testing guide](testing.md) for the evidence required by change type.

## Phase 35 completion snapshot

The Phase 35 completion gate was recorded on 2026-10-24 against the
`phase/iban-checksum-verification` branch, stacked on `phase/line-item-completeness`.

Environment:

- Windows with Python 3.12.12;
- uv 0.9.13;
- GitHub Actions Ubuntu runner; and
- a clean Git worktree before and after the gate.

Verified results:

| Gate | Result |
| --- | --- |
| `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` | Clean (zero whitespace errors) |
| `uv lock --check` | Lockfile and project metadata agree |
| `uv run pip-audit` | Passed (0 known vulnerabilities; `veridoc` skipped as not on PyPI) |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | All 313 files formatted |
| `uv run mypy` | No issues found across 120 source files |
| `uv run pytest --cov=veridoc` | 1430 passed; total branch coverage 94.06% (90% floor) |
| `uv run pytest tests/test_documentation.py` | Local Markdown links, documented test-module inventory, and tracked whitespace hygiene test passed |
| `uv build --clear` | Built wheel and source distribution |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content, entry-point, and path-safety validation |
| Isolated wheel smoke test | Passed isolated installation and API verification |
| Isolated sdist smoke test | Passed isolated build, installation, and API verification |
