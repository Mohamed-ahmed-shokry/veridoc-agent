# Phase 25 Progress Record: Non-Positive Line Item Detection

## Phase Overview

- **Phase:** Phase 25
- **Goal:** Implement deterministic `non_positive_line_item` verification rule to detect line items with zero or negative amounts, quantities, or unit prices.
- **Status:** In Progress
- **Branch:** `phase/non-positive-line-items`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Update `docs/roadmap.md` and create `docs/PROGRESS.md` | Done | `d72a132` |
| 2 | Record ADR 0032 (`docs/decisions/0032-non-positive-line-item-detection.md`) & index | Done | `3e40443` |
| 3 | Add `non_positive_line_item` to `FindingType` & model unit tests | Done | `db74988` |
| 4 | Implement `check_non_positive_line_items` in `veridoc.verification.line_item_amounts` | Done | `4650091` |
| 5 | Integrate `check_non_positive_line_items` into `VerificationService.verify()` | Done | Pending |
| 6 | Add comprehensive test suite in `tests/test_verification_line_item_amounts.py` | Not Started | |
| 7 | Update `docs/testing.md` test inventory | Not Started | |
| 8 | Update `docs/architecture.md` | Not Started | |
| 9 | Update `AGENTS.md` | Not Started | |
| 10 | Update `CHANGELOG.md` | Not Started | |
| 11 | Update `docs/release-evidence.md` completion snapshot & roadmap links | Not Started | |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `non_positive_line_item` in `FindingType` union and accepted by `VerificationFinding` | Verified | `test_verification_models.py::test_verification_finding_accepts_non_positive_line_item` |
| 2 | Pure function returns findings for non-positive line items (high for negative, medium for zero) and empty for positive or absent values | Pending | |
| 3 | `VerificationService` includes non-positive line item findings in output | Pending | |
| 4 | Non-positive line item findings drive processing verdict to `review_required` | Pending | |
| 5 | All non-positive line item tests pass and full quality gate passes without regression | Pending | |
| 6 | `test_documentation.py` validates updated test-module inventory and links | Pending | |

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
- Focused checks: Pending.
- Linter/Typecheck: Clean at baseline.

## Blockers

None.
