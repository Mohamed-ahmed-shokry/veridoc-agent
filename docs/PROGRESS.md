# Phase 26 Progress Record: Invoice Header Monetary Bounds

## Phase Overview

- **Phase:** Phase 26
- **Goal:** Implement deterministic `non_positive_subtotal`, `negative_tax`, and `invalid_discount` verification rules in `veridoc.verification.header_amounts` to catch non-positive subtotals, negative taxes, negative discounts, and discounts exceeding the invoice subtotal.
- **Status:** In Progress
- **Branch:** `phase/header-monetary-bounds`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 26 invoice header monetary bounds in `docs/roadmap.md` | Done | `9a8bd7f` |
| 2 | Initialize Phase 26 progress record and decision log in `docs/PROGRESS.md` | In Progress | Pending |
| 3 | Record ADR 0033 (`docs/decisions/0033-invoice-header-monetary-bounds.md`) | Pending | - |
| 4 | Register ADR 0033 in `docs/decisions/README.md` and link in `docs/roadmap.md` | Pending | - |
| 5 | Add `non_positive_subtotal` to `FindingType` in `src/veridoc/verification/models.py` | Pending | - |
| 6 | Add `non_positive_subtotal` model test in `tests/test_verification_models.py` | Pending | - |
| 7 | Add `negative_tax` to `FindingType` in `src/veridoc/verification/models.py` | Pending | - |
| 8 | Add `negative_tax` model test in `tests/test_verification_models.py` | Pending | - |
| 9 | Add `invalid_discount` to `FindingType` in `src/veridoc/verification/models.py` | Pending | - |
| 10 | Add `invalid_discount` model test in `tests/test_verification_models.py` | Pending | - |
| 11 | Implement `check_non_positive_subtotal` in `src/veridoc/verification/header_amounts.py` | Pending | - |
| 12 | Add unit tests for `check_non_positive_subtotal` in `tests/test_verification_header_amounts.py` and register in `docs/testing.md` | Pending | - |
| 13 | Implement `check_negative_tax` in `src/veridoc/verification/header_amounts.py` | Pending | - |
| 14 | Add unit tests for `check_negative_tax` in `tests/test_verification_header_amounts.py` | Pending | - |
| 15 | Implement `check_invalid_discount` (negative discount check) in `src/veridoc/verification/header_amounts.py` | Pending | - |
| 16 | Add unit tests for negative discount detection in `tests/test_verification_header_amounts.py` | Pending | - |
| 17 | Extend `check_invalid_discount` to detect discounts exceeding positive subtotal | Pending | - |
| 18 | Add unit tests for discount exceeding subtotal in `tests/test_verification_header_amounts.py` | Pending | - |
| 19 | Implement `check_header_amounts` composition function in `src/veridoc/verification/header_amounts.py` | Pending | - |
| 20 | Add composition, multi-finding, and immutability tests in `tests/test_verification_header_amounts.py` | Pending | - |
| 21 | Integrate `check_header_amounts` into `VerificationService.verify()` | Pending | - |
| 22 | Add `VerificationService`, `ExplanationService`, and `derive_verdict` integration tests in `tests/test_verification_header_amounts.py` | Pending | - |
| 23 | Update `docs/architecture.md` to document Phase 26 header monetary rules | Pending | - |
| 24 | Update `AGENTS.md` to reflect Phase 26 completion and test inventory | Pending | - |
| 25 | Update `README.md` phase status and verification summary for Phase 26 | Pending | - |
| 26 | Update `CHANGELOG.md` with Phase 26 deliverables | Pending | - |
| 27 | Record Phase 26 verified completion snapshot in `docs/release-evidence.md` and `docs/roadmap.md` | Pending | - |
| 28 | Finalize `docs/PROGRESS.md` with complete commit hashes and validation results | Pending | - |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `non_positive_subtotal`, `negative_tax`, and `invalid_discount` in `FindingType` union and accepted by `VerificationFinding` | Pending | - |
| 2 | `check_non_positive_subtotal` returns `high` severity for `subtotal < 0`, `medium` for `subtotal == 0`, and `[]` for `subtotal > 0` or `None` | Pending | - |
| 3 | `check_negative_tax` returns `high` severity for `tax < 0` and `[]` for `tax >= 0` or `None` | Pending | - |
| 4 | `check_invalid_discount` returns `high` severity for `discount < 0` and for `discount > subtotal` (when `subtotal > 0`), and `[]` for `0 <= discount <= subtotal` or `None` | Pending | - |
| 5 | `VerificationService.verify()` includes header amount findings and drives processing verdict to `review_required` | Pending | - |
| 6 | Full quality gate (`pytest --cov=veridoc`, `mypy`, `ruff`, `pip-audit`, distribution checks, smoke tests, `test_documentation.py`) passes without regression | Pending | - |

## Decision Log

### Decision 1: Scope of Phase 26 — Invoice Header Monetary Bounds (`subtotal`, `tax`, `discount`)
- **Context:** Phase 24 (`non_positive_invoice_total`, ADR 0031) and Phase 25 (`non_positive_line_item`, ADR 0032) added positivity checks for the invoice total and individual line items. Phase 25's decision log explicitly deferred header-level `tax` and `discount` bounds to a dedicated phase because header fields have distinct accounting semantics and OCR failure modes. In addition, `invoice.subtotal` lacked a positivity check when `line_items` or `tax`/`discount` are omitted, or when a zero/negative subtotal is offset by tax.
- **Decision:** Implement a cohesive `veridoc.verification.header_amounts` module (ADR 0033) enforcing three deterministic header invariants:
  1. `non_positive_subtotal`: `invoice.subtotal > 0` (`high` severity for `< 0`, `medium` severity for `== 0`).
  2. `negative_tax`: `invoice.tax >= 0` (`high` severity for `< 0`; `0` is valid for tax-exempt/zero-rated supplies).
  3. `invalid_discount`: `invoice.discount >= 0` and (when `subtotal > 0`) `invoice.discount <= invoice.subtotal` (`high` severity).
- **Alternatives Considered:**
  1. *Flag `tax == 0` or `discount == 0` as medium severity.* Rejected: Unlike `total` and `subtotal`, zero tax (`0.00`) and zero discount (`0.00`) are normal on commercial invoices (tax-exempt/reverse-charge invoices and undiscounted invoices). Flagging zero tax or zero discount would create massive false positives and break existing corpus and unit tests.
  2. *Collapse all three checks into a single generic finding type.* Rejected: Distinct `FindingType` values (`non_positive_subtotal`, `negative_tax`, `invalid_discount`) give reviewers and downstream evaluation metrics clear, actionable attribution for each distinct accounting violation.
- **Blast Radius & Reversibility:** Pure deterministic verification rules with no database schema migrations, no API route changes, and full backward compatibility.

## Validation Results

- Baseline suite: 1252 tests passing (`ruff check .`, `ruff format --check .`, `mypy` all clean).
- Phase 26 final validation: Pending completion.

## Blockers

None.
