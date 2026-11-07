# Phase 37 Progress Record: ISO 4217 Currency Code Verification

## Phase Overview

- **Phase:** Phase 37
- **Goal:** Introduce deterministic ISO 4217 three-letter currency code verification (ADR 0043) for extracted invoice currency, catching OCR misreads, hallucinated alphabetic symbols, and non-standard abbreviations, routing invalid currency codes to review.
- **Status:** Complete
- **Branch:** `phase/currency-code-verification`
- **Draft PR:** [#16](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/pull/16)
- **Base:** `phase/vat-format-verification` (stacked on Phase 36)

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 37 specification in `docs/roadmap.md` and record ADR 0043 | Completed | `955a7f7`, `8a16490` |
| 2 | Register ADR 0043 in the decisions index | Completed | `f31efb9` |
| 3 | Add `invalid_currency` to `FindingType` with a model test | Completed | `2a9454a`, `874c6b3` |
| 4 | Add authoritative ISO 4217 currency code table | Completed | `90b4d35` |
| 5 | Implement `check_currency_code` rule | Completed | `90b4d35` |
| 6 | Add unit tests covering all paths and input immutability | Completed | `1cbf1fa` |
| 7 | Register test module in documentation | Completed | `144503b` |
| 8 | Integrate rule into `VerificationService.verify()` | Completed | `07c4e68` |
| 9 | Add `VerificationService` integration and verdict tests | Completed | `0dcfc35` |
| 10 | Update README, CHANGELOG, architecture, AGENTS, and roadmap | Completed | `553bc10`..`aaef954` |
| 11 | Verify local CI parity and record release evidence | Completed | `f2c65ca` |
| 12 | Finalize progress record with validation evidence | Completed | this commit |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `invalid_currency` appears in `FindingType` and is accepted by `VerificationFinding` | Verified | `tests/test_verification_models.py` passed |
| 2 | Recognized ISO 4217 currency codes (including casing and whitespace variants) produce no finding | Verified | `tests/test_verification_currency.py` passed |
| 3 | Unrecognized three-letter currency strings produce one `medium` finding with `field="currency"` and `currency` set to the normalized value | Verified | `tests/test_verification_currency.py` passed |
| 4 | Absent and empty currency codes produce no finding (deferred to required-field completeness verification) | Verified | `tests/test_verification_currency.py` passed |
| 5 | The check does not mutate the input extraction | Verified | `tests/test_verification_currency.py` passed |
| 6 | `VerificationService.verify()` reports the finding and routes the verdict to `review_required` | Verified | `tests/test_verification_currency.py` passed |
| 7 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | 1531 tests passed locally; quality gate green |

## Decision Log

### Decision 1: Validate against authoritative ISO 4217 three-letter codes
- **Context:** OCR misreads frequently produce non-existent currency codes (e.g., `XYZ`, `USO`, `DLR`, `ZZZ`, `INV`) or hallucinated abbreviations. Invoices with invalid currency codes corrupt financial downstream settlement.
- **Decision:** Implement `check_currency_code` in `veridoc.verification.currency` using a frozenset of all standard three-letter ISO 4217 currency codes (`ISO_4217_CURRENCY_CODES`).
- **Alternatives Considered:** Allowing arbitrary strings or validating only major trading currencies (USD, EUR, GBP). Rejected: international invoices use diverse global currencies; restricting to a subset would cause false positives.
- **Blast Radius & Reversibility:** Pure function, additive finding type, no schema or API changes.

### Decision 2: Ignore absent and empty currency values
- **Context:** An omitted currency is a document completeness gap, already detected by Phase 33's required invoice field completeness check (`missing_field` finding for `currency`).
- **Decision:** Return `[]` without finding when `invoice.currency` is `None` or empty.
- **Alternatives Considered:** Emitting `invalid_currency` for empty values. Rejected: would produce redundant findings alongside `missing_field`.
- **Blast Radius & Reversibility:** Clean separation of concerns between format verification and completeness verification.

### Decision 3: Assign `medium` severity to `invalid_currency` findings
- **Context:** An unrecognized currency prevents safe automated reconciliation and ledger posting, requiring operator review.
- **Decision:** Assign `medium` severity to `invalid_currency`, routing the verdict to `review_required` in `derive_verdict`.
- **Alternatives Considered:** `high` severity. Rejected: reserving `high` for critical payment redirection (bank mismatch) or invalid document types.
- **Blast Radius & Reversibility:** Fully consistent with the verification severity framework.

## CI & Validation Log

Local commands run from the repository root on Windows with Python 3.12.12 and uv 0.9.13:

| Command | Result |
|---|---|
| `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` | Passed (zero whitespace issues) |
| `uv lock --check` | Passed |
| `uv run pip-audit` | Passed (0 known vulnerabilities; `veridoc` skipped as not on PyPI) |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | Passed (316 files formatted) |
| `uv run mypy` | Passed (122 source files) |
| `uv run pytest -q` | 1531 passed |
| `uv run pytest --cov=veridoc` | 1531 passed; 94.09% total branch coverage (90% floor) |
| `uv run pytest tests/test_documentation.py` | 3 passed |
| `uv build --clear` | Wheel and source distribution built |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content and safety checks |
| Isolated wheel smoke test | Passed |
| Isolated source distribution smoke test | Passed |

Remote CI:

- Workflow: CI
- Run: [42386763803](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/actions/runs/42386763803)
- Head commit: `7f7e488`
- Result: success
