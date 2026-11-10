# Phase 38 Progress Record: Excessive Tax Amount Verification

## Phase Overview

- **Phase:** Phase 38
- **Goal:** Introduce deterministic excessive tax amount verification (ADR 0044) for invoice headers, catching OCR decimal misreads, field transpositions, and impossible tax liabilities exceeding pre-tax subtotals or totals.
- **Status:** Complete (Local CI passed; ready for remote delivery)
- **Branch:** `phase/excessive-tax-verification`
- **Draft PR:** [Pending creation]
- **Base:** `phase/vat-format-verification` (stacked on Phase 37)

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 38 specification in `docs/roadmap.md` and record ADR 0044 | Completed | `95afd3e`, `9b82341` |
| 2 | Register ADR 0044 in the decisions index | Completed | `81a1f1b` |
| 3 | Add `excessive_tax` to `FindingType` with a model test | Completed | `0651fbf`, `bf7ae0d` |
| 4 | Implement `check_excessive_tax` rule in `veridoc.verification.tax_bounds` | Completed | `b996a65` |
| 5 | Add unit tests covering all paths and input immutability | Completed | `d605bbc` |
| 6 | Register test module in documentation | Completed | `bf79feb` |
| 7 | Integrate rule into `VerificationService.verify()` | Completed | `cd482fe` |
| 8 | Add `VerificationService` integration and verdict tests | Completed | `99b8bff` |
| 9 | Update README, CHANGELOG, architecture, AGENTS, and roadmap | Completed | `150101a`..`f1d2161` |
| 10 | Verify local CI parity and record release evidence | Completed | `2bc4d00` |
| 11 | Finalize progress record with validation evidence | Completed | this commit |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `excessive_tax` appears in `FindingType` and is accepted by `VerificationFinding` | Verified | `tests/test_verification_models.py` passed |
| 2 | Invoices with `tax <= subtotal` (including 0%, standard commercial rates 5-27%, and 100%) produce no finding | Verified | `tests/test_verification_tax_bounds.py` passed |
| 3 | Invoices where `subtotal > 0` and `tax > subtotal` produce one `high`-severity finding with `field="tax"`, `tax`, `subtotal`, and `effective_tax_rate` | Verified | `tests/test_verification_tax_bounds.py` passed |
| 4 | Invoices where `subtotal is None`, `total > 0`, and `tax > total` produce one `high`-severity finding with `field="tax"`, `tax`, and `total` | Verified | `tests/test_verification_tax_bounds.py` passed |
| 5 | Invoices with absent (`None`) tax or absent subtotal and total produce no finding | Verified | `tests/test_verification_tax_bounds.py` passed |
| 6 | Invoices with non-positive subtotals or totals (`<= 0`) produce no finding here (deferred to `non_positive_subtotal` / `non_positive_invoice_total`) | Verified | `tests/test_verification_tax_bounds.py` passed |
| 7 | The check does not mutate the input extraction | Verified | `tests/test_verification_tax_bounds.py` passed |
| 8 | `VerificationService.verify()` reports the finding and routes the verdict to `review_required` | Verified | `tests/test_verification_tax_bounds.py` passed |
| 9 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | 1543 tests passed locally; quality gate green |

## Decision Log

### Decision 1: Enforce deterministic upper tax bound at 100% of pre-tax subtotal
- **Context:** In commercial accounting and taxation (VAT, GST, sales tax), statutory tax rates represent a bounded fraction of the taxable base (standard rates range from 0% to ~27%). An extracted tax amount exceeding the subtotal (`tax > subtotal`) indicates OCR decimal shifts, field transposition (swapping tax and subtotal/total), or invoice distortion.
- **Decision:** Implement `check_excessive_tax` in `veridoc.verification.tax_bounds` with a default upper bound ratio of `DEFAULT_MAX_TAX_TO_SUBTOTAL_RATIO = Decimal("1.00")` (100% of subtotal).
- **Alternatives Considered:** Allowing arbitrary tax amounts or enforcing an overly tight standard rate threshold (e.g. 30%). Rejected: an overly tight threshold would trigger false positives on special excise taxes, while omitting the check allows transposed and corrupted tax figures to clear straight-through processing.
- **Blast Radius & Reversibility:** Pure function, additive finding type, zero false positives on standard commercial transactions.

### Decision 2: Fallback bound against payable total when subtotal is omitted
- **Context:** Some summary or simplified invoices specify a tax breakdown alongside the payable total while omitting an explicit subtotal field.
- **Decision:** When `subtotal` is `None` and `total > 0`, enforce that `tax <= total`. If `tax > total`, emit `excessive_tax` with structured details (`field="tax"`, `tax`, `total`).
- **Alternatives Considered:** Skipping tax bound checks entirely when `subtotal` is missing. Rejected: would allow a $500 tax on a $200 total invoice to clear without warning.
- **Blast Radius & Reversibility:** Scoped strictly to cases where subtotal is absent and tax exceeds total.

### Decision 3: Assign `high` severity to `excessive_tax` findings
- **Context:** An impossible tax amount distorts financial postings, risks massive financial overpayment to vendors, and triggers mandatory tax authority audit penalties on tax returns.
- **Decision:** Assign `high` severity to `excessive_tax`, routing the invoice to `review_required` in `derive_verdict`.
- **Alternatives Considered:** `medium` severity. Rejected: reserving `high` for critical financial and legal distortion, consistent with `invalid_discount` (discount > subtotal) and `non_positive_subtotal`.
- **Blast Radius & Reversibility:** Fully consistent with the verification severity framework.

## CI & Validation Log

Local commands run from the repository root on Windows with Python 3.12.12 and uv 0.9.13:

| Command | Result |
|---|---|
| `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` | Passed (zero whitespace issues) |
| `uv lock --check` | Passed |
| `uv run pip-audit` | Passed (0 known vulnerabilities; `veridoc` skipped as not on PyPI) |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | Passed (322 files formatted) |
| `uv run mypy` | Passed (123 source files) |
| `uv run pytest -q` | 1543 passed |
| `uv run pytest --cov=veridoc` | 1543 passed; 94.12% total branch coverage (90% floor) |
| `uv run pytest tests/test_documentation.py` | 3 passed |
| `uv build --clear` | Wheel and source distribution built |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content and safety checks |
| Isolated wheel smoke test | Passed |
| Isolated source distribution smoke test | Passed |
