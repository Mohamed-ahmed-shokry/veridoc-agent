# Phase 49 Progress Record: Cumulative PO Line-Item Quantity Ceiling Verification

## Phase Overview

- **Phase:** Phase 49
- **Goal:** Extend `check_purchase_order_ceiling` in `veridoc.verification.purchase_orders` so split invoices against a single purchase order cannot cumulatively exceed any line item's authorized quantity even when cumulative header totals remain within the overall PO total (ADR 0055).
- **Status:** Complete
- **Branch:** `phase/po-line-item-quantity-ceiling`
- **Draft PR:** [#28](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/pull/28)
- **Base:** `main`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 49 specification in `docs/roadmap.md` | Completed | `ae5e28d` |
| 2 | Record ADR 0055 in `docs/decisions/0055-cumulative-po-line-item-quantity-ceiling.md` | Completed | `27f1046` |
| 3 | Register ADR 0055 in `docs/decisions/README.md` | Completed | `7aa37db` |
| 4 | Add `_authorized_po_line_quantities` helper in `src/veridoc/verification/purchase_orders.py` | Completed | `ef3eb53` |
| 5 | Add `_prior_po_line_quantities` helper in `src/veridoc/verification/purchase_orders.py` | Completed | `e92de88` |
| 6 | Implement `_check_line_item_quantity_ceilings` in `src/veridoc/verification/purchase_orders.py` | Completed | `be90ea9` |
| 7 | Enforce line-item quantity ceilings in `check_purchase_order_ceiling` | Completed | `d6f07f0` |
| 8 | Add unit tests for split over-billing, within-ceiling acceptance, and no-prior passthrough | Completed | `b1affd4` |
| 9 | Add unit tests for repeated PO keys, omitted PO qty, and currency/PO filtering | Completed | `be1551d` |
| 10 | Add immutability and SQLite `VerificationService` + verdict integration test | Completed | `723be74` |
| 11 | Update documentation (`docs/architecture.md`, `CHANGELOG.md`, `README.md`, `AGENTS.md`) | Completed | `48de5e7`, `a92ad49`, `adade04`, `9da5062` |
| 12 | Mark Phase 49 complete in `docs/roadmap.md` status table and approval rule | Completed | `3e6d1c6` |
| 13 | Record Phase 49 completion snapshot in `docs/release-evidence.md` | Completed | `dcd5230` |
| 14 | Finalize progress record with validation evidence | Completed | this commit |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | Split invoices exceeding one PO line item's authorized quantity emit `high`-severity `purchase_order_mismatch` (`field="purchase_order_billed_line_item_quantity"`, `line_item_key`, `prior_invoice_count`) even under PO total | Verified | `test_purchase_order_ceiling_flags_split_line_item_over_billing_under_po_total` passed |
| 2 | Split invoices at or below authorized line-item quantity emit `[]` | Verified | `test_purchase_order_ceiling_accepts_split_line_item_at_or_below_authorized_qty` passed |
| 3 | Single-invoice line-item over-billing with zero prior invoices emits `[]` from `check_purchase_order_ceiling` | Verified | `test_purchase_order_ceiling_skips_line_item_over_billing_without_prior_history` passed |
| 4 | Multi-line POs sum repeated `line_item_key` quantities; omitted (`None`) PO quantity excludes that key | Verified | `test_purchase_order_ceiling_sums_repeated_po_keys_without_header_total` and `test_purchase_order_ceiling_ignores_other_pos_incompatible_currencies_and_none_po_qty` passed |
| 5 | Other POs and incompatible currencies are ignored; POs without header totals still enforce line-item ceilings | Verified | `tests/test_verification_purchase_orders.py` passed (18 passed; 95.02% branch coverage on `purchase_orders.py`) |
| 6 | Input `InvoiceExtraction`, `PurchaseOrder`, and `history` remain strictly immutable | Verified | `test_purchase_order_ceiling_preserves_immutability_and_routes_to_review` passed |
| 7 | `VerificationService.verify()` routes cumulative line-item quantity over-billing to `review_required` | Verified | Real `SQLiteInvoiceRepository` + `VerificationService.verify()` + `derive_verdict` test passed |
| 8 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | Local CI parity green (1790 passed, 94.38% branch coverage); remote CI run `46094168790` green and re-verified on final HEAD |

## Decision Log

### Decision 1: Reuse `purchase_order_mismatch` with `details["field"] = "purchase_order_billed_line_item_quantity"`
- **Context:** ADR 0026 models all purchase-order authorization violations under `purchase_order_mismatch`, distinguishing header totals (`total`), single-invoice quantities (`line_item_quantity`), and cumulative header totals (`purchase_order_billed_total`) via `details["field"]`.
- **Decision:** Keep the uniform `purchase_order_mismatch` (`high`) contract and set `details={"field": "purchase_order_billed_line_item_quantity", "line_item_key": key, "prior_invoice_count": prior_count}`.
- **Alternatives Considered:** Adding a new `FindingType` literal. Rejected to stay consistent with ADR 0026 and avoid fragmenting PO mismatch consumers.
- **Blast Radius & Reversibility:** Localized to `_check_line_item_quantity_ceilings` in `src/veridoc/verification/purchase_orders.py`.

### Decision 2: Conservatively exclude PO keys where any PO line omits `quantity`, and evaluate independently of header `total`
- **Context:** Some POs specify line items without a header total (`PO-002`, `PO-003`), while other POs may omit `quantity` on one of multiple lines sharing a key.
- **Decision:** Run `_check_line_item_quantity_ceilings` whenever `_comparable_amounts(invoice, purchase_order)` holds (even if `purchase_order.total` or `invoice.total` is `None`), sum repeated PO keys, and exclude any key where a PO line has `quantity is None`.
- **Alternatives Considered:** Gating line-item ceilings behind `purchase_order.total is not None` or treating `None` PO quantities as `0`. Rejected because the former misses line-item-only POs and the latter causes false positives.
- **Blast Radius & Reversibility:** Pure helpers in `src/veridoc/verification/purchase_orders.py` with zero schema changes.

## Validation & CI Log

- `git diff --check "$(git hash-object -t tree /dev/null)" HEAD`: Clean (0 errors)
- `uv lock --check`: Passed (Resolved 103 packages)
- `uv run pip-audit`: Passed (0 vulnerabilities; `veridoc` skipped)
- `uv run ruff check .`: Passed (All checks passed!)
- `uv run ruff format --check .`: Passed (343 files already formatted)
- `uv run mypy`: Passed (0 issues across 128 source files)
- `uv run pytest --cov=veridoc`: Passed (1790 passed in 50.96s, 94.38% branch coverage, 90.0% floor)
- `uv run pytest tests/test_documentation.py`: Passed (3 passed)
- `uv build --clear`: Built `veridoc-0.1.0-py3-none-any.whl` and `veridoc-0.1.0.tar.gz`
- `uv run twine check dist/*`: Both distributions passed metadata validation
- `uv run python scripts/check_distribution.py`: Both archives passed content, entry-point, and path safety
- Isolated wheel smoke test: Passed
- Isolated sdist smoke test: Passed
- Remote GitHub Actions CI (`ci.yml`): Passed (`46094168790`, 1m52s) on `phase/po-line-item-quantity-ceiling` Draft PR #28; final HEAD run verified after push.
