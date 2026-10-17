# Phase 30 Progress Record: Excessive Credit Window and Due Date Bound Verification

## Phase Overview

- **Phase:** Phase 30
- **Goal:** Introduce deterministic excessive credit window and due date bound verification (ADR 0036) detecting invoices whose credit window (`due_date - invoice_date`) exceeds 365 calendar days (`MAXIMUM_CREDIT_WINDOW_DAYS = 365`), preventing vision/OCR year hallucinations and multi-year zombie liabilities from evading review.
- **Status:** Complete
- **Branch:** `phase/excessive-due-date-window`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Record ADR 0036 in `docs/decisions/` and index | Completed | `7448b65` |
| 2 | Define Phase 30 specification in `docs/roadmap.md` | Completed | `dd625a7` |
| 3 | Initialize `docs/PROGRESS.md` for Phase 30 | Completed | `893c489` |
| 4 | Add `excessive_due_date_window` to `FindingType` in `src/veridoc/verification/models.py` | Completed | `2dddbe2` |
| 5 | Add unit tests for `excessive_due_date_window` in `tests/test_verification_models.py` | Completed | `b012c6e` |
| 6 | Implement `MAXIMUM_CREDIT_WINDOW_DAYS` and `check_excessive_due_date_window` in `src/veridoc/verification/due_date_bounds.py` | Completed | `66f2cfa` |
| 7 | Add unit tests in `tests/test_verification_due_date_bounds.py` covering standard, boundary, and excessive credit windows | Completed | `6d44887` |
| 8 | Integrate `check_excessive_due_date_window` into `VerificationService.verify()` | Completed | `1a7c097` |
| 9 | Add immutability, service integration, and verdict tests in `tests/test_verification_due_date_bounds.py` | Completed | `53a8970`, `299d078` |
| 10 | Update `docs/testing.md` test inventory and guide | Completed | `78566de` |
| 11 | Update `docs/architecture.md`, `AGENTS.md`, and `README.md` | Completed | `b85f0e7`, `fd3a07e`, `3628c4b` |
| 12 | Update `CHANGELOG.md` for Phase 30 | Completed | `88c5142` |
| 13 | Fix formatting and style in `tests/test_verification_due_date_bounds.py` | Completed | `ae45e54` |
| 14 | Record Phase 30 completion snapshot in `docs/release-evidence.md` | Completed | `cc2ae1a` |
| 15 | Finalize `docs/PROGRESS.md` and verify full CI parity | Completed | `99259d0` |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `excessive_due_date_window` appears in `FindingType` and is accepted by `VerificationFinding` | Verified | `tests/test_verification_models.py` passed |
| 2 | `check_excessive_due_date_window` returns `[]` when `invoice_date` or `due_date` is None, when `due_date < invoice_date`, or when `(due_date - invoice_date).days <= 365` | Verified | `tests/test_verification_due_date_bounds.py` passed |
| 3 | `check_excessive_due_date_window` returns one `excessive_due_date_window` finding (`severity="medium"`) when `(due_date - invoice_date).days > 365` | Verified | `tests/test_verification_due_date_bounds.py` passed |
| 4 | `check_excessive_due_date_window` does not mutate input `InvoiceExtraction` | Verified | `tests/test_verification_due_date_bounds.py` passed |
| 5 | `VerificationService.verify()` includes findings and routes violating invoices to `review_required` | Verified | `tests/test_verification_due_date_bounds.py` passed |
| 6 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | Ruff, mypy, pytest, pip-audit, twine, smoke tests pass |

## Decision Log

### Decision 1: Scope of Phase 30 — Excessive Credit Window Verification (ADR 0036)
- **Context:** Following Phase 28 (payment terms consistency) and Phase 29 (CI gate restoration), invoices without explicit payment terms or with unparseable terms could still carry multi-year due dates (e.g., misreading 2026 as 2036 or confusing due dates with warranty expirations).
- **Decision:** Establish `MAXIMUM_CREDIT_WINDOW_DAYS = 365` (1 year) as the maximum allowable commercial credit window. Invoices exceeding this threshold are flagged with `excessive_due_date_window` (`severity="medium"`).
- **Alternatives Considered:** (a) Shorter threshold (e.g. 180 days). Rejected: Complex capital goods, seasonal agricultural trade, and sovereign vendor contracts occasionally use Net 180 or Net 360 terms. 365 days represents an objective bound where any exceeding duration is unequivocally abnormal for trade credit. (b) Flagging in arithmetic `check_invoice_dates`. Rejected: Separation of concerns; `check_invoice_dates` handles only local order (`invoice_date <= due_date`).
- **Blast Radius & Reversibility:** Zero breaking changes to existing models; purely additive verification check.

## Validation Results

- Tracked whitespace check: `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` passed (exit code 0).
- Linter & Formatter: `ruff check .` and `ruff format --check .` passed cleanly.
- Type Checker: `mypy` passed with 0 errors across all source files.
- Test suite: All unit and integration tests passing, branch coverage >= 90% floor.
- Documentation tests: Markdown links, documented test-module inventory, and tracked whitespace hygiene test passed.
- Vulnerability Audit: `pip-audit` passed with 0 vulnerabilities found.
- Distribution Build & Twine: `uv build --clear` and `twine check dist/*` passed.
- Distribution Smoke Tests: isolated wheel and sdist smoke tests passed.

## Blockers

None.
