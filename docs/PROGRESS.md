# Phase 45 Progress Record: Vendor Name and Registry Consistency Verification

## Phase Overview

- **Phase:** Phase 45
- **Goal:** Implement deterministic verification that extracted `vendor_name` is consistent with the resolved `VendorEntity`'s registered `legal_name` and `aliases` when entity resolution succeeds via tax ID, bank account, or canonical identifier (ADR 0051).
- **Status:** Complete
- **Branch:** `phase/vendor-name-consistency-verification`
- **Draft PR:** [#24](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/pull/24)
- **Base:** `main`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 45 specification in `docs/roadmap.md` | Completed | `9702417` |
| 2 | Record ADR 0051 in `docs/decisions/0051-vendor-name-consistency-verification.md` | Completed | `2924715` |
| 3 | Register ADR 0051 in `docs/decisions/README.md` | Completed | `b735690` |
| 4 | Add `vendor_name_mismatch` to `FindingType` in `src/veridoc/verification/models.py` | Completed | `029f847` |
| 5 | Add model acceptance test in `tests/test_verification_models.py` | Completed | `6adf0b5` |
| 6 | Implement `check_vendor_name` in `src/veridoc/verification/vendor_rules.py` | Completed | `9a479ae` |
| 7 | Integrate `check_vendor_name` into `check_vendor_registry` | Completed | `aa7444b` |
| 8 | Add unit and `VerificationService` integration tests in `tests/test_verification_vendor_rules.py` | Completed | `164bcab` |
| 9 | Update documentation (`README.md`, `CHANGELOG.md`, `docs/architecture.md`, `AGENTS.md`) | Completed | `acfb11b`, `085c475`, `a1592da`, `ae46e9b` |
| 10 | Mark Phase 45 complete in `docs/roadmap.md` approval rule and phase table | Completed | `5d681ba` |
| 11 | Record Phase 45 completion snapshot in `docs/release-evidence.md` | Completed | `c112b9b` |
| 12 | Finalize progress record with validation evidence | Completed | this commit |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `vendor_name_mismatch` is a valid `FindingType` literal union member | Verified | `tests/test_verification_models.py` passed (26 passed) |
| 2 | Unresolved, `vendor=None`, or absent/blank `vendor_name` emits `[]` | Verified | `tests/test_verification_vendor_rules.py` passed (12 passed) |
| 3 | Exact `legal_name` matches emit `[]` | Verified | `tests/test_verification_vendor_rules.py` passed |
| 4 | Registered `aliases` matches emit `[]` | Verified | `tests/test_verification_vendor_rules.py` passed |
| 5 | Token-reordered or fuzzy matches (`>= 0.85`) emit `[]` | Verified | `tests/test_verification_vendor_rules.py` passed |
| 6 | Divergent `vendor_name` on tax/bank/ID-resolved vendor emits `vendor_name_mismatch` (`medium`) | Verified | `tests/test_verification_vendor_rules.py` passed |
| 7 | Input `InvoiceExtraction` and `VendorEntity` remain strictly immutable | Verified | `tests/test_verification_vendor_rules.py` passed |
| 8 | `check_vendor_registry()` and `VerificationService.verify()` route to `review_required` | Verified | `tests/test_verification_vendor_rules.py` + end-to-end SQLite check passed |
| 9 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | Local CI parity green (1768 passed, 94.29% coverage); remote CI verified after push |

## Decision Log

### Decision 1: Reuse `calculate_token_similarity` and `derive_canonical_vendor_key`
- **Context:** `veridoc.vendors.resolution` already implements token-sorted fuzzy similarity (`calculate_token_similarity`) with `fuzzy_threshold=0.85` and `veridoc.vendors.models` implements `derive_canonical_vendor_key`.
- **Decision:** Reuse both functions directly in `check_vendor_name` rather than duplicating string normalization or similarity logic.
- **Alternatives Considered:** Writing a separate Levenshtein/substring helper in `vendor_rules.py`. Rejected: violates DRY and risks divergence between resolution and verification thresholds.
- **Blast Radius & Reversibility:** Pure function in `veridoc.verification.vendor_rules`.

### Decision 2: Medium severity for `vendor_name_mismatch`
- **Context:** Trade names, DBA names, or abbreviated supplier names not yet added to `aliases` can differ from legal names without indicating fraud, whereas bank/tax mismatches are `high` severity.
- **Decision:** Assign `severity="medium"`, which routes the invoice to `review_required` while reserving `high` for direct payment/tax coordinate contradictions.
- **Alternatives Considered:** `high` severity. Rejected: preserves the established severity hierarchy.
- **Blast Radius & Reversibility:** Single literal in `check_vendor_name`.

## Validation & CI Log

- `git diff --check "$(git hash-object -t tree /dev/null)" HEAD`: Clean (0 errors)
- `uv lock --check`: Passed (Resolved 103 packages)
- `uv run pip-audit`: Passed (0 vulnerabilities; `veridoc` skipped)
- `uv run ruff check .`: Passed (All checks passed!)
- `uv run ruff format --check .`: Passed (339 files formatted)
- `uv run mypy`: Passed (0 issues across 128 source files)
- `uv run pytest --cov=veridoc`: Passed (1768 passed in 38.57s, 94.29% branch coverage, 90.0% floor)
- `uv run pytest tests/test_documentation.py`: Passed (3 passed)
- `uv build --clear`: Built `veridoc-0.1.0-py3-none-any.whl` and `veridoc-0.1.0.tar.gz`
- `uv run twine check dist/*`: Both distributions passed metadata validation
- `uv run python scripts/check_distribution.py`: Both archives passed content, entry-point, and path safety
- Isolated wheel smoke test: Passed
- Isolated sdist smoke test: Passed
