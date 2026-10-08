# Phase 25 Progress Record: Non-Positive Line Item Detection

## Phase Overview

- **Phase:** Phase 25
- **Goal:** Implement deterministic `non_positive_line_item` verification rule to detect line items with zero or negative amounts, quantities, or unit prices.
- **Status:** Complete
- **Branch:** `phase/non-positive-line-items`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Update `docs/roadmap.md` and create `docs/PROGRESS.md` | Done | `d72a132` |
| 2 | Record ADR 0032 (`docs/decisions/0032-non-positive-line-item-detection.md`) & index | Done | `3e40443` |
| 3 | Add `non_positive_line_item` to `FindingType` & model unit tests | Done | `db74988` |
| 4 | Implement `check_non_positive_line_items` in `veridoc.verification.line_item_amounts` | Done | `4650091` |
| 5 | Integrate `check_non_positive_line_items` into `VerificationService.verify()` | Done | `0ff3960` |
| 6 | Add comprehensive test suite in `tests/test_verification_line_item_amounts.py` | Done | `893b789` |
| 7 | Update `docs/testing.md` test inventory | Done | `4c589bc` |
| 8 | Update `docs/architecture.md` | Done | `11ccfc0` |
| 9 | Update `AGENTS.md` | Done | `f816d58` |
| 10 | Update `CHANGELOG.md` | Done | `18192d3` |
| 11 | Update `docs/release-evidence.md` completion snapshot & roadmap links | Done | Pending |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `non_positive_line_item` in `FindingType` union and accepted by `VerificationFinding` | Verified | `test_verification_models.py::test_verification_finding_accepts_non_positive_line_item` |
| 2 | Pure function returns findings for non-positive line items (high for negative, medium for zero) and empty for positive or absent values | Verified | `test_verification_line_item_amounts.py` (27 unit tests) |
| 3 | `VerificationService` includes non-positive line item findings in output | Verified | `test_verification_line_item_amounts.py::test_verification_service_includes_negative_line_item_finding`, `test_verification_service_includes_zero_line_item_finding` |
| 4 | Non-positive line item findings drive processing verdict to `review_required` | Verified | `test_verification_line_item_amounts.py::test_verdict_derivation_drives_review_required_for_negative_line_item`, `test_verdict_derivation_drives_review_required_for_zero_line_item` |
| 5 | All non-positive line item tests pass and full quality gate passes without regression | Verified | 1252 pytest tests passed (31.31s), 93.76% branch coverage, ruff clean, mypy clean |
| 6 | `test_documentation.py` validates updated test-module inventory and links | Verified | `tests/test_documentation.py` passed (2/2) |

## Decision Log

### Decision 1: Scope of Phase 25 — Non-Positive Line Item Detection
- **Context:** Following Phase 24's invoice total positivity check (`total > 0`), individual line items within an invoice were still unconstrained. Invoices with positive totals but containing negative line items (unauthorized credit lines, returns, trade-ins) or zero line items (promotional items or OCR price dropouts) previously received an unearned `clear` verdict.
- **Decision:** Introduce a deterministic `non_positive_line_item` verification rule evaluating `quantity`, `unit_price`, and `total_price` for each line item. Negative values yield `high` severity; zero values yield `medium` severity. Null/absent values are ignored as extraction completeness matters.
- **Alternatives Considered:**
  1. *Include negative tax and discount bounds in this phase.* Rejected: Tax and discount apply at the invoice header level, whereas line items are discrete transaction items with distinct accounting controls and OCR failure modes. Keeping line items cohesive and dedicated preserves modularity.
  2. *Emit separate findings per field on the same line item.* Rejected: Emitting one finding per offending line item with combined field details avoids finding spam for compound line items (e.g. quantity -1 and total -10).
- **Blast Radius & Reversibility:** Pure function addition, zero database migrations or API endpoint breaking changes; fully backward compatible.

## Validation Results

- Baseline suite: 1224 tests passing.
- Focused checks: 27 unit tests passing in `tests/test_verification_line_item_amounts.py`.
- Documentation tests: 2 tests passing in `tests/test_documentation.py`.
- Complete test suite: 1252 tests passing (31.31s).
- Branch coverage: 93.76% (minimum floor: 90.0%).
- Linter (`ruff check .`): All checks passed.
- Formatter (`ruff format --check .`): 288 files already formatted.
- Type checker (`mypy`): Success (0 issues in 112 source files).
- Lockfile (`uv lock --check`): Resolved and verified.
- Distribution build: Wheel and sdist built cleanly with `uv build --clear`.
- Twine metadata check: Both distributions PASSED metadata check.
- Distribution contents check: Validated archive contents and paths.
- Smoke tests: Isolated wheel and sdist both passed `scripts/smoke_distribution.py`.
- CLI help smoke: All 5 maintenance CLIs loaded cleanly.
- Git whitespace: `git diff --check` clean.

## Blockers

None.
