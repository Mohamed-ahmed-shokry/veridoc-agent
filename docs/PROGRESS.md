# Phase 27 Progress Record: Invoice Arithmetic Tolerances and Fractional Rounding Bounds

## Phase Overview

- **Phase:** Phase 27
- **Goal:** Implement deterministic commercial rounding tolerance (`DEFAULT_ROUNDING_TOLERANCE = Decimal("0.02")`) and discrepancy classification (`rounding_discrepancy` with `severity="low"`, retaining `high`-severity mismatch findings for material errors > 0.02) and omitted discount/tax normalization in `veridoc.verification.arithmetic`.
- **Status:** In Progress
- **Branch:** `phase/header-arithmetic-tolerances`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 27 in `docs/roadmap.md` and record ADR 0034 in `docs/decisions/` and `docs/decisions/README.md` | In Progress | Pending |
| 2 | Initialize Phase 27 progress record and decision log in `docs/PROGRESS.md` | In Progress | Pending |
| 3 | Add `rounding_discrepancy` to `FindingType` in `src/veridoc/verification/models.py` | Pending | Pending |
| 4 | Add `rounding_discrepancy` model test in `tests/test_verification_models.py` | Pending | Pending |
| 5 | Update `_check_invoice_total` in `src/veridoc/verification/arithmetic.py` to support `DEFAULT_ROUNDING_TOLERANCE`, omitted discount/tax handling, and `rounding_discrepancy` findings | Pending | Pending |
| 6 | Add comprehensive invoice total rounding and tolerance unit tests in `tests/test_verification_arithmetic.py` | Pending | Pending |
| 7 | Update `_check_line_item_amounts` and `_check_line_items_subtotal` in `src/veridoc/verification/arithmetic.py` with rounding tolerance and discrepancy classification | Pending | Pending |
| 8 | Add line-item amounts and line-items subtotal rounding and tolerance unit tests in `tests/test_verification_arithmetic.py` | Pending | Pending |
| 9 | Add verification service, verdict derivation, and immutability tests in `tests/test_verification_arithmetic.py` | Pending | Pending |
| 10 | Update `docs/testing.md` and `docs/architecture.md` for Phase 27 | Pending | Pending |
| 11 | Update `AGENTS.md`, `README.md`, and `CHANGELOG.md` for Phase 27 | Pending | Pending |
| 12 | Record release evidence in `docs/release-evidence.md` and finalize `docs/PROGRESS.md` | Pending | Pending |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `rounding_discrepancy` appears in `FindingType` and is accepted by `VerificationFinding` | Pending | Target: `tests/test_verification_models.py` |
| 2 | When discrepancy is between `0` and `0.02` inclusive, arithmetic checks emit `rounding_discrepancy` with `severity="low"` and structured details | Pending | Target: `tests/test_verification_arithmetic.py` |
| 3 | When discrepancy strictly exceeds `0.02`, arithmetic checks emit material mismatch findings (`invoice_total_mismatch`, `line_item_amount_mismatch`, `line_items_subtotal_mismatch`) with `severity="high"` | Pending | Target: `tests/test_verification_arithmetic.py` |
| 4 | When `discount` is omitted (`None`) but `subtotal`, `tax`, and `total` are present, `check_invoice_total` correctly evaluates `subtotal + tax == total` rather than skipping | Pending | Target: `tests/test_verification_arithmetic.py` |
| 5 | Full quality gate passes without regression | Pending | Release gate |

## Decision Log

### Decision 1: Scope of Phase 27 — Invoice Arithmetic Tolerances and Fractional Rounding Bounds
- **Context:** Veridoc's arithmetic rules previously enforced exact, zero-tolerance decimal equality for `subtotal + tax - discount == total`, `quantity * unit_price == total_price`, and `sum(line_item.total_price) == subtotal`. Under international commercial invoicing and tax standards (Peppol BIS 3.0 / EN 16931 rules BR-CO-10/15), independent rounding of line items, fractional unit prices, and fractional tax rates routinely create 1-cent or 2-cent ($0.01 - $0.02) penny rounding differences. Previously, Veridoc flagged any difference—even $0.01—as a `high`-severity mismatch, halting automation. In addition, `_check_invoice_total` skipped entirely whenever `discount` was `None` (omitted on >90% of commercial invoices), allowing massive discrepancies on standard undiscounted invoices to evade detection.
- **Decision:**
  1. Define `DEFAULT_ROUNDING_TOLERANCE = Decimal("0.02")` (2 minor units).
  2. Add `rounding_discrepancy` finding type with `severity="low"`, emitted for `0 < discrepancy <= 0.02`.
  3. Retain `high`-severity mismatch findings (`invoice_total_mismatch`, `line_item_amount_mismatch`, `line_items_subtotal_mismatch`) for material errors `> 0.02`.
  4. Normalize omitted `discount` to `Decimal(0)` when `subtotal`, `tax`, and `total` are present, and omitted `tax` to `Decimal(0)` when `discount` is present.
- **Alternatives Considered:**
  1. *Silently ignore discrepancies <= 0.02 without emitting any finding.* Rejected: Accounting transparency and review audit trails require recording that a rounding difference was observed, even if it is low-severity and does not block approval.
  2. *Only apply tolerance to the header invoice total.* Rejected: Line item totals (`quantity * unit_price`) and line-items sum (`sum(total_price) == subtotal`) suffer from the exact same fractional rounding realities. A comprehensive tolerance applies consistently across all three arithmetic relations.
- **Blast Radius & Reversibility:** Pure deterministic verification rules with no database schema migrations, no API route changes, and full backward compatibility.

## Validation Results

- Baseline suite: 1296 tests passing.

## Blockers

None.
