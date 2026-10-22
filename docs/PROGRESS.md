# Phase 33 Progress Record: Required Invoice Field Completeness Verification

## Phase Overview

- **Phase:** Phase 33
- **Goal:** Introduce deterministic required invoice field completeness verification (ADR 0039) requiring `invoice_number`, `invoice_date`, `currency`, and `total`, preventing sparse or empty extractions from receiving an unearned `clear` verdict when every field-dependent rule is skipped.
- **Status:** Complete
- **Branch:** `phase/required-field-completeness`
- **Draft PR:** [#9](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/pull/9)

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 33 specification in `docs/roadmap.md` and record ADR 0039 | Completed | `3cabb3a` |
| 2 | Register ADR 0039 in the decisions index | Completed | `0ab6cd6` |
| 3 | Add `missing_required_field` to `FindingType` with a model test | Completed | `ef2cf74` |
| 4 | Implement `REQUIRED_INVOICE_FIELDS` and `check_required_fields` | Completed | `1a9efa9` |
| 5 | Add focused completeness unit tests | Completed | `de04f3c` |
| 6 | Integrate completeness first in `VerificationService.verify()` | Completed | `1aff49e` |
| 7 | Add service integration and verdict tests | Completed | `eb9bcee` |
| 8 | Update existing graph, service, integration, evaluation, review, and rule fixtures | Completed | `c4690be`..`f24ea9f` |
| 9 | Update the documented test inventory | Completed | `f1b5573` |
| 10 | Update architecture, AGENTS, README, and CHANGELOG documentation | Completed | `572a898`..`b3413ed`, `069d618` |
| 11 | Upgrade vulnerable Pillow and certifi versions | Completed | `13bf33e` |
| 12 | Verify local CI parity and record release evidence | Completed | `a9c1265` |
| 13 | Push branch, open draft PR, and verify remote CI | Completed | CI run `39518432117` |
| 14 | Mark Phase 33 complete in the roadmap and finalize this record | Completed | this commit |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `missing_required_field` appears in `FindingType` and is accepted by `VerificationFinding` | Verified | `tests/test_verification_models.py` passed |
| 2 | `check_required_fields` returns `[]` when all four required fields are present | Verified | `tests/test_verification_completeness.py` passed |
| 3 | One finding per absent field, in fixed order, with documented severities and `details={"field": ...}` | Verified | `tests/test_verification_completeness.py` passed |
| 4 | A completely empty extraction yields four findings and cannot clear | Verified | `tests/test_verification_completeness.py` passed |
| 5 | The check does not mutate the input extraction | Verified | `tests/test_verification_completeness.py` passed |
| 6 | `VerificationService.verify()` reports completeness findings and routes to `review_required` | Verified | `tests/test_verification_completeness.py` passed |
| 7 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | Local gates below; CI run [39518432117](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/actions/runs/39518432117) success |

## Decision Log

### Decision 1: Require the four fields every identity/date/money rule depends on
- **Context:** Each existing deterministic rule is conditional on its input fields. Locally, `check_duplicate_invoice_number`, date rules, total rules, and same-currency history comparisons all return nothing when their fields are absent, so an empty `InvoiceExtraction(document_type="invoice")` cleared all checks.
- **Decision:** Require `invoice_number`, `invoice_date`, `currency`, and `total`; emit `missing_required_field` findings for absent values.
- **Alternatives Considered:** (a) Have each rule report its own missing input. Rejected: duplicated findings and still vacuous for rules not wired to a field. (b) Require every schema field. Rejected: legitimate invoices omit due date, terms, subtotal, tax, discount, and line items. (c) Reject sparse extractions before verification. Rejected: verification owns trust decisions and review snapshots must retain evidence.
- **Blast Radius & Reversibility:** Additive rule and finding type; no schema, persistence, prompt, or route change.

### Decision 2: Fixed field order and per-field severities
- **Context:** Reviewers and evidence bundles need stable, field-addressable findings; severity should reflect financial impact.
- **Decision:** Emit in the order `invoice_number`, `invoice_date`, `currency`, `total`; use `high` for identity (`invoice_number`) and payable amount (`total`), and `medium` for issue date and currency.
- **Alternatives Considered:** A single aggregate `incomplete_invoice` finding. Rejected: loses field-level structure and stable ordering.
- **Blast Radius & Reversibility:** Finding order is deterministic and covered by tests, so later changes are explicit.

### Decision 3: Exclude vendor identity and optional commercial fields
- **Context:** Missing vendor identity already emits `insufficient_history` and an absent vendor resolution, while optional fields are legitimately absent on many invoices.
- **Decision:** Do not duplicate vendor-identity findings and do not require `due_date`, `payment_terms`, `subtotal`, `tax`, `discount`, or line items.
- **Alternatives Considered:** Requiring vendor name/identifier for completeness. Rejected: duplicates existing evidence and changes no verdict outcome.
- **Blast Radius & Reversibility:** Keeps the rule small and avoids systematic false positives.

### Decision 4: Complete existing fixtures with the newly required fields
- **Context:** Several graph, processing, evaluation, and review integration fixtures used minimal extractions that previously cleared because the missing fields skipped every rule. Requiring the fields surfaced those assumptions.
- **Decision:** Add the required values (and, where a test needs a clear verdict, comparable history) so each fixture continues to test its original behavior. Update evaluation ground truth and evidence to include the invoice date.
- **Alternatives Considered:** Weakening assertions or exempting fixtures. Rejected: that would hide the behavior change the phase exists to make.
- **Blast Radius & Reversibility:** Test-only changes; no production behavior beyond the new rule.

### Decision 5: Upgrade Pillow and certifi for auditability
- **Context:** `pip-audit` reported newly published advisories against the locked Pillow 12.3.0 and certifi 2026.7.22. CI runs the audit, so the baseline would be red regardless of Phase 33 code.
- **Decision:** Raise the Pillow lower bound to `>=13.0.0`, upgrade certifi to 2026.10.19, and relock. Full tests passed with Pillow 13.0.0.
- **Alternatives Considered:** Ignoring or suppressing advisories. Rejected: forbidden CI weakening and a real security regression.
- **Blast Radius & Reversibility:** Two transitive/direct dependency versions; no API change used by Veridoc.

## CI & Validation Log

Local commands run from the repository root on Windows with Python 3.12.12 and uv 0.9.13:

| Command | Result |
|---|---|
| `git diff --check "4b825dc642cb6eb9a060e54bf8d69288fbee4904" HEAD` | Passed (no output) |
| `uv lock --check` | Passed |
| `uv run pip-audit` | Passed after dependency upgrade (0 vulnerabilities) |
| `uv run ruff check .` | Passed |
| `uv run ruff format --check .` | Passed (307 files) |
| `uv run mypy` | Passed (118 source files) |
| `uv run pytest -q` | 1379 passed |
| `uv run pytest --cov=veridoc` | 1379 passed; 94.01% total branch coverage |
| `uv run pytest tests/test_documentation.py` | 3 passed |
| `uv build --clear` | Wheel and source distribution built |
| `uv run twine check dist/*` | Both distributions passed |
| `uv run python scripts/check_distribution.py` | Both archives passed |
| Isolated wheel smoke test | Passed |
| Isolated source-distribution smoke test | Passed |

Remote CI:

- Workflow: `CI`
- Run: [39518432117](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/actions/runs/39518432117)
- Head commit: `13bf33e`
- Result: `success`

The container-build step runs only in GitHub Actions; local Docker is not
installed. The remote run completed that step successfully.

## Blockers

None. Phase 14 remains planned but blocked on a Tesseract-equipped operator
environment and is out of scope for this phase.
