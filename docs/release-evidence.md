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

## Evidence boundaries

The repository workflow reproduces the dependency, audit, quality, test,
coverage, build, distribution, isolated wheel and source-distribution, and
full-tree whitespace gates on GitHub-hosted Ubuntu runners. Markdown-link
validation, the maintenance CLI smoke, and the final clean-worktree check remain
local evidence. No hosted CI result was observed during this local completion
run. This snapshot therefore does not claim a remote CI pass, deployment
readiness, live provider execution, or accuracy on a representative invoice
corpus. Tests use deterministic fakes for external OCR and model boundaries.

See the [development guide](development.md) for the reproducible commands and
the [testing guide](testing.md) for the evidence required by change type.
