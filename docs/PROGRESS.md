# Phase 35 Progress Record: Vendor Bank Account Checksum Verification

## Phase Overview

- **Phase:** Phase 35
- **Goal:** Introduce deterministic ISO 13616 IBAN structure and ISO 7064 mod-97-10 checksum verification (ADR 0041) for extracted vendor bank accounts, routing corrupted OCR reads and fabricated remit-to accounts to review independently of vendor registry availability.
- **Status:** Complete
- **Branch:** `phase/iban-checksum-verification`
- **Draft PR:** [#11](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/pull/11)
- **Base:** `phase/line-item-completeness` (stacked on Phase 34, PR #10); retarget to `main` after Phase 34 merges.

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 35 specification in `docs/roadmap.md` and record ADR 0041 | Completed | `db40036` |
| 2 | Register ADR 0041 in the decisions index | Completed | `490554a` |
| 3 | Add `invalid_bank_account` to `FindingType` with a model test | Completed | `336b447`, `23d9095` |
| 4 | Add the IBAN country length table and mod-97 helper with tests | Completed | `ce1330a`, `6257bda`, `bb1bfd9` |
| 5 | Resolve CI filelock dependency vulnerability via lockfile upgrade | Completed | `e5d7d20` |
| 6 | Implement `check_bank_account_checksum` rule | Completed | `e22b3a0` |
| 7 | Add unit tests covering all paths and input immutability | Completed | `54bc429` |
| 8 | Integrate rule into `VerificationService.verify()` | Completed | `9b22f9d` |
| 9 | Add `VerificationService` integration and verdict tests | Completed | `705b4d0` |
| 10 | Update test fixtures with verified valid IBAN checksums | Completed | `7f79b5f` |
| 11 | Update README, CHANGELOG, architecture, AGENTS, and roadmap | Completed | `384ae74`..`3a57e55` |
| 12 | Verify local CI parity and record release evidence | Completed | `faba18c` |
| 13 | Fix EOF whitespace in release evidence | Completed | `c1b4aef` |
| 14 | Finalize progress record with green CI run 40123775767 | Completed | this commit |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `invalid_bank_account` appears in `FindingType` and is accepted by `VerificationFinding` | Verified | `tests/test_verification_models.py` passed |
| 2 | A valid IBAN (spaced or compact, mixed case, hyphenated) produces no finding | Verified | `tests/test_verification_bank_account.py` passed |
| 3 | An IBAN-shaped value with an invalid checksum produces one `high` finding with `details` carrying normalized account and `reason="checksum"` | Verified | `tests/test_verification_bank_account.py` passed |
| 4 | An IBAN-shaped value whose length differs from the country length produces one `high` finding with `reason="length"` | Verified | `tests/test_verification_bank_account.py` passed |
| 5 | Absent, blank, and non-IBAN-shaped (domestic) accounts produce no finding | Verified | `tests/test_verification_bank_account.py` passed |
| 6 | The check does not mutate the input extraction | Verified | `tests/test_verification_bank_account.py` passed |
| 7 | `VerificationService.verify()` reports the finding and routes to `review_required` | Verified | `tests/test_verification_bank_account.py` passed |
| 8 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | 1430 tests passed locally; CI run [40123775767](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/actions/runs/40123775767) success |

## Decision Log

### Decision 1: Validate IBAN structure and mod-97 remainder for IBAN-shaped accounts
- **Context:** OCR models frequently misread a digit or character in long IBAN strings, and malicious actors often forge accounts without calculating the mod-97 check digits. Vendor registry reconciliation rules only run when reference data is loaded and the vendor is known.
- **Decision:** Implement `check_bank_account_checksum` in `veridoc.verification.bank_account` using the ISO 13616 country length table and ISO 7064 mod-97 remainder algorithm. Check length before checksum and emit at most one finding per invoice.
- **Alternatives Considered:** Relying solely on vendor registry matching. Rejected: leaves invoices without matched master data vulnerable to corrupted or fabricated accounts.
- **Blast Radius & Reversibility:** Pure function, additive finding type, no schema or API changes.

### Decision 2: Ignore non-IBAN and domestic account numbers
- **Context:** Many domestic accounts use local routing and account numbering conventions that do not conform to IBAN format (e.g. US routing/account numbers, UK sort code + account number).
- **Decision:** Only evaluate strings that match `^[A-Z]{2}[0-9]{2}[A-Z0-9]+$` and whose first two characters are a recognized country code in `IBAN_COUNTRY_LENGTHS`. All other strings (and absent/blank values) return `[]`.
- **Alternatives Considered:** Flagging any non-IBAN account as invalid. Rejected: causes false positives on valid domestic remittances.
- **Blast Radius & Reversibility:** Scoped strictly to recognizable IBAN formats.

### Decision 3: Assign `high` severity to invalid bank account findings
- **Context:** An account number that fails country length or mod-97 check digits is structurally impossible and guaranteed to fail payment processing or represent invoice tampering.
- **Decision:** Assign `high` severity to `invalid_bank_account`, guaranteeing routing to `review_required` in `derive_verdict`.
- **Alternatives Considered:** `medium` severity. Rejected: invalid remit-to coordinates present direct payment redirection risk.
- **Blast Radius & Reversibility:** Consistent with `vendor_bank_account_mismatch` severity.

### Decision 4: Upgrade `filelock` dependency to resolve CI security audit
- **Context:** Remote CI failed at `uv run pip-audit` due to CVE-2026-112940, CVE-2026-112913, and CVE-2026-112907 published against `filelock==3.32.4`.
- **Decision:** Execute `uv lock --upgrade-package filelock` upgrading to `4.2.4` and commit the updated `uv.lock`.
- **Alternatives Considered:** Ignoring audit failure or disabling pip-audit. Rejected: violates Rule #2 and CI honesty.
- **Blast Radius & Reversibility:** Lockfile-only change, verified safe across entire test suite.

### Decision 5: Stack Phase 35 on Phase 34 branch
- **Context:** Phase 34 is complete on `phase/line-item-completeness` with PR #10 open and approved. Phase 35 follows Phase 34 in sequence.
- **Decision:** Branch `phase/iban-checksum-verification` from `phase/line-item-completeness` and open Draft PR #11 with base `phase/line-item-completeness`.
- **Alternatives Considered:** Branching from `main`. Rejected: would introduce conflicts in shared documentation and roadmap files.
- **Blast Radius & Reversibility:** Clean branch hierarchy; easily retargeted to `main` when Phase 34 merges.

## CI & Validation Log

Local commands run from the repository root on Windows with Python 3.12.12 and uv 0.9.13:

| Command | Result |
|---|---|
| `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` | Passed (zero whitespace issues) |
| `uv lock --check` | Passed |
| `uv run pip-audit` | Passed (0 known vulnerabilities; `veridoc` skipped as not on PyPI) |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | Passed (313 files formatted) |
| `uv run mypy` | Passed (120 source files) |
| `uv run pytest -q` | 1430 passed |
| `uv run pytest --cov=veridoc` | 1430 passed; 94.06% total branch coverage (90% floor) |
| `uv run pytest tests/test_documentation.py` | 3 passed |
| `uv build --clear` | Wheel and source distribution built |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content and safety checks |
| Isolated wheel smoke test | Passed |
| Isolated source distribution smoke test | Passed |

Remote CI:

- Workflow: `CI`
- Run: [40123775767](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/actions/runs/40123775767)
- Head commit: `c1b4aef`
- Result: `success`

## Blockers

None. Phase 14 remains planned but blocked on a Tesseract-equipped operator environment and is out of scope for this phase.
