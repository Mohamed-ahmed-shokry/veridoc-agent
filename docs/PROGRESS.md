# Phase 27 Progress Record: Invoice Arithmetic Tolerances and Fractional Rounding Bounds

## Phase Overview

- **Phase:** Phase 27
- **Goal:** Implement deterministic commercial rounding tolerance (`DEFAULT_ROUNDING_TOLERANCE = Decimal("0.02")`) and discrepancy classification (`rounding_discrepancy` with `severity="low"`, retaining `high`-severity mismatch findings for material errors > 0.02) and omitted discount/tax normalization in `veridoc.verification.arithmetic`.
- **Status:** Complete
- **Branch:** `phase/header-arithmetic-tolerances`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 27 in `docs/roadmap.md` | Done | `0e460f3` |
| 2 | Record ADR 0034 in `docs/decisions/` and `docs/decisions/README.md` | Done | `c4e180d` |
| 3 | Initialize Phase 27 progress record and decision log in `docs/PROGRESS.md` | Done | `0d19d91` |
| 4 | Add `rounding_discrepancy` to `FindingType` in `src/veridoc/verification/models.py` | Done | `535b491` |
| 5 | Add `rounding_discrepancy` model test in `tests/test_verification_models.py` | Done | `a2efae9` |
| 6 | Add `DEFAULT_ROUNDING_TOLERANCE` and update `check_invoice_total` with rounding bounds and omitted field handling in `src/veridoc/verification/arithmetic.py` | Done | `8e068ea` |
| 7 | Update `check_line_item_amounts` and `check_line_items_subtotal` with rounding tolerance and discrepancy classification in `src/veridoc/verification/arithmetic.py` | Done | `70a447e` |
| 8 | Update `docs/architecture.md` and `docs/testing.md` for Phase 27 | Done | This commit |
| 9 | Update `AGENTS.md`, `README.md`, and `CHANGELOG.md` for Phase 27 | Done | This commit |
| 10 | Record release evidence in `docs/release-evidence.md` and finalize `docs/PROGRESS.md` | Done | This commit |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `rounding_discrepancy` appears in `FindingType` and is accepted by `VerificationFinding` | Verified | Tested in `tests/test_verification_models.py` |
| 2 | When discrepancy is between `0` and `0.02` inclusive, arithmetic checks emit `rounding_discrepancy` with `severity="low"` and structured details | Verified | Tested across invoice total, line item amounts, and line items subtotal in `tests/test_verification_arithmetic.py` |
| 3 | When discrepancy strictly exceeds `0.02`, arithmetic checks emit material mismatch findings (`invoice_total_mismatch`, `line_item_amount_mismatch`, `line_items_subtotal_mismatch`) with `severity="high"` | Verified | Tested in `tests/test_verification_arithmetic.py` |
| 4 | When `discount` is omitted (`None`) but `subtotal`, `tax`, and `total` are present, `check_invoice_total` correctly evaluates `subtotal + tax == total` rather than skipping | Verified | Tested in `tests/test_verification_arithmetic.py` |
| 5 | Full quality gate passes without regression | Verified | Complete release gate executed clean |

## Decision Log

### Decision 1: Scope of Phase 27 — Invoice Arithmetic Tolerances and Fractional Rounding Bounds
- **Context:** Veridoc's arithmetic rules previously enforced exact, zero-tolerance decimal equality for `subtotal + tax - discount == total`, `quantity * unit_price == total_price`, and `sum(line_item.total_price) == subtotal`. Under international commercial invoicing and tax standards (Peppol BIS 3.0 / EN 16931 rules BR-CO-10/15), independent rounding of line items, fractional unit prices, and fractional tax rates routinely create 1-cent or 2-cent ($0.01 - $0.02) penny rounding differences. Previously, Veridoc flagged any difference—even $0.01—as a `high`-severity mismatch, halting automation. In addition, `_check_invoice_total` skipped entirely whenever `discount` was `None` (omitted on >90% of commercial invoices), allowing massive discrepancies on standard undiscounted invoices to evade detection.
- **Decision:**
  1. Define `DEFAULT_ROUNDING_TOLERANCE = Decimal("0.02")` (2 minor units).
  2. Add `rounding_discrepancy` finding type with `severity="low"`, emitted for `0 < discrepancy <= 0.02`.
  3. Retain `high`-severity mismatch findings (`invoice_total_mismatch`, `line_item_amount_mismatch`, `line_items_subtotal_mismatch`) for material errors `> 0.02`.
  4. Normalize omitted `discount` to `Decimal(0)` when `subtotal`, `tax`, and `total` are present, and omitted `tax` to `Decimal(0)` when `discount` is present.
  5. Export public functions `check_invoice_total`, `check_line_item_amounts`, `check_line_items_subtotal`, and `check_invoice_dates` alongside `check_arithmetic`.
- **Alternatives Considered:**
  1. *Silently ignore discrepancies <= 0.02 without emitting any finding.* Rejected: Accounting transparency and review audit trails require recording that a rounding difference was observed, even if it is low-severity and does not block approval.
  2. *Only apply tolerance to the header invoice total.* Rejected: Line item totals (`quantity * unit_price`) and line-items sum (`sum(total_price) == subtotal`) suffer from the exact same fractional rounding realities. A comprehensive tolerance applies consistently across all three arithmetic relations.
- **Blast Radius & Reversibility:** Pure deterministic verification rules with no database schema migrations, no API route changes, and full backward compatibility.

## Validation Results

- Baseline suite: 1296 tests passing.
- Phase 27 test suite: 22 tests passing in `tests/test_verification_arithmetic.py` (19 new tests added).
- Total test suite: 1315 tests passing.
- Quality gate checks:
  - `uv run ruff check .` passed.
  - `uv run ruff format --check .` passed.
  - `uv run mypy` passed.
  - `uv run pip-audit` passed.
  - `uv build --clear` and `twine check dist/*` passed.
  - `check_distribution.py` and `smoke_distribution.py` passed.
  - `test_documentation.py` passed.

## Blockers

None.
