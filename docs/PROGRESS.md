# Phase 46 Progress Record: Historical Currency Consistency Verification

## Phase Overview

- **Phase:** Phase 46
- **Goal:** Implement deterministic verification that an invoice's extracted `currency` matches the vendor's consistent historical invoicing currency when at least `MINIMUM_HISTORY_SAMPLE_SIZE` (3) prior invoices share one currency (ADR 0052).
- **Status:** Complete
- **Branch:** `phase/historical-currency-consistency`
- **Draft PR:** [#25](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/pull/25)
- **Base:** `main`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 46 specification in `docs/roadmap.md` | Completed | `25b43a2` |
| 2 | Record ADR 0052 in `docs/decisions/0052-historical-currency-consistency-verification.md` | Completed | `4bb4b8f` |
| 3 | Register ADR 0052 in `docs/decisions/README.md` | Completed | `1829fff` |
| 4 | Add `historical_currency_mismatch` to `FindingType` in `src/veridoc/verification/models.py` | Completed | `c5907f0` |
| 5 | Add model acceptance test in `tests/test_verification_models.py` | Completed | `211afc0` |
| 6 | Implement `check_historical_currency` in `src/veridoc/verification/field_history.py` | Completed | `cc0b01a` |
| 7 | Integrate `check_historical_currency` into `VerificationService.verify()` | Completed | `71c0b15` |
| 8 | Add unit and `VerificationService` integration tests in `tests/test_verification_field_history.py` | Completed | `0e78477`, `683d40e` |
| 9 | Update documentation (`README.md`, `CHANGELOG.md`, `docs/architecture.md`, `AGENTS.md`) | Completed | `829b2ec`, `8390098`, `ab4d0bd`, `bdd819c` |
| 10 | Mark Phase 46 complete in `docs/roadmap.md` approval rule and phase table | Completed | `bae2363` |
| 11 | Record Phase 46 completion snapshot in `docs/release-evidence.md` | Completed | `4938c02` |
| 12 | Finalize progress record with validation evidence | Completed | this commit |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `historical_currency_mismatch` is a valid `FindingType` literal union member | Verified | `tests/test_verification_models.py` passed (27 passed) |
| 2 | Absent `invoice.currency` (`None`) emits `[]` | Verified | `tests/test_verification_field_history.py` passed (6 passed) |
| 3 | Sparse history (< 3 currency observations) emits `[]` | Verified | `tests/test_verification_field_history.py` passed |
| 4 | Multi-currency history emits `[]` | Verified | `tests/test_verification_field_history.py` passed |
| 5 | Consistent currency match (including normalization) emits `[]` | Verified | `tests/test_verification_field_history.py` passed |
| 6 | Currency mismatch against consistent history emits `historical_currency_mismatch` (`medium`) | Verified | `tests/test_verification_field_history.py` passed |
| 7 | Input `InvoiceExtraction` and `history` remain strictly immutable | Verified | `tests/test_verification_field_history.py` passed |
| 8 | `VerificationService.verify()` routes mismatched invoices to `review_required` | Verified | `tests/test_verification_field_history.py` + end-to-end SQLite check passed |
| 9 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | Local CI parity green (1772 passed, 94.31% coverage); remote CI verified after push |

## Decision Log

### Decision 1: Do not emit duplicate `insufficient_history` in `check_historical_currency`
- **Context:** Both `check_historical_total` and `check_payment_terms` already emit `insufficient_history` (`info`) when fewer than `MINIMUM_HISTORY_SAMPLE_SIZE` (3) observations exist.
- **Decision:** Return `[]` when fewer than 3 historical currency observations exist, avoiding duplicate `insufficient_history` noise.
- **Alternatives Considered:** Emitting an additional `insufficient_history` finding for currency. Rejected: clutters review UI and breaks existing tests that assert exact `insufficient_history` counts.
- **Blast Radius & Reversibility:** Pure function in `veridoc.verification.field_history`.

### Decision 2: Skip multi-currency vendors (`len(set(historical_currencies)) != 1`)
- **Context:** International suppliers may legitimately bill in multiple currencies (e.g., USD and EUR).
- **Decision:** Only flag `historical_currency_mismatch` when all prior currency observations (sample size >= 3) share a single consistent currency.
- **Alternatives Considered:** Majority-vote currency threshold. Rejected: would cause false positives for legitimate dual-currency vendors.
- **Blast Radius & Reversibility:** Single condition in `check_historical_currency`.

## Validation & CI Log

- `git diff --check "$(git hash-object -t tree /dev/null)" HEAD`: Clean (0 errors)
- `uv lock --check`: Passed (Resolved 103 packages)
- `uv run pip-audit`: Passed (0 vulnerabilities; `veridoc` skipped)
- `uv run ruff check .`: Passed (All checks passed!)
- `uv run ruff format --check .`: Passed (340 files formatted)
- `uv run mypy`: Passed (0 issues across 128 source files)
- `uv run pytest --cov=veridoc`: Passed (1772 passed in 83.21s, 94.31% branch coverage, 90.0% floor)
- `uv run pytest tests/test_documentation.py`: Passed (3 passed)
- `uv build --clear`: Built `veridoc-0.1.0-py3-none-any.whl` and `veridoc-0.1.0.tar.gz`
- `uv run twine check dist/*`: Both distributions passed metadata validation
- `uv run python scripts/check_distribution.py`: Both archives passed content, entry-point, and path safety
- Isolated wheel smoke test: Passed
- Isolated sdist smoke test: Passed
