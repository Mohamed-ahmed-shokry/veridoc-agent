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

## Evidence boundaries

The repository workflow reproduces these gates on GitHub-hosted Ubuntu runners,
but no hosted CI result was observed during this local completion run. This
snapshot therefore does not claim a remote CI pass, deployment readiness, live
provider execution, or accuracy on a representative invoice corpus. Tests use
deterministic fakes for external OCR and model boundaries.

See the [development guide](development.md) for the reproducible commands and
the [testing guide](testing.md) for the evidence required by change type.
