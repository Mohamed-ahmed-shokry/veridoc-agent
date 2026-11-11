# Phase 39 Progress Record: Invoice Number Format & Placeholder Verification

## Phase Overview

- **Phase:** Phase 39
- **Goal:** Introduce deterministic invoice number format, placeholder, label, and length bound verification (ADR 0045) for invoice headers, catching OCR hallucinations, default templates, blank/punctuation tokens, non-printable control characters, and runaway strings.
- **Status:** Complete
- **Branch:** `phase/invoice-number-verification`
- **Base:** `phase/excessive-tax-verification` (stacked on Phase 38)

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 39 specification in `docs/roadmap.md` and record ADR 0045 | Completed | `e73e887`, `b06667a` |
| 2 | Register ADR 0045 in the decisions index | Completed | `e171566` |
| 3 | Add `invalid_invoice_number` to `FindingType` with a model test | Completed | `d4c6af6`, `7835f24` |
| 4 | Implement `check_invoice_number_format` rule in `veridoc.verification.invoice_number` | Completed | `7d9e305` |
| 5 | Add unit tests covering all paths and input immutability | Completed | `db2b877` |
| 6 | Register test module in documentation | Completed | `45fc721` |
| 7 | Integrate rule into `VerificationService.verify()` | Completed | `5a0434c` |
| 8 | Add `VerificationService` integration and verdict tests | Completed | `c0f919d` |
| 9 | Update README, CHANGELOG, architecture, AGENTS, and roadmap | Completed | `0abde52`..`2e9944d` |
| 10 | Verify local CI parity and record release evidence | Completed | `0dfa4df` |
| 11 | Finalize progress record with validation evidence | Completed | this commit |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `invalid_invoice_number` appears in `FindingType` and is accepted by `VerificationFinding` | Verified | `tests/test_verification_models.py` passed |
| 2 | Clean, legitimate alphanumeric invoice numbers produce no finding | Verified | `tests/test_verification_invoice_number.py` passed |
| 3 | Invoices with placeholder numbers (`N/A`, `NONE`, `NULL`, `UNKNOWN`, `TBD`, `PENDING`, `VOID`, `SAMPLE`) produce one `high`-severity finding with `reason="placeholder"` | Verified | `tests/test_verification_invoice_number.py` passed |
| 4 | Invoices with generic header labels (`INVOICE`, `INVOICE NUMBER`, `INV #`, `BILL NO`, `NUMBER`) produce one `high`-severity finding with `reason="generic_label"` | Verified | `tests/test_verification_invoice_number.py` passed |
| 5 | Invoices with blank or pure punctuation strings (`"-"`, `"---"`, `"."`, `"/"`, `"   "`) produce one `high`-severity finding with `reason="blank_or_punctuation"` | Verified | `tests/test_verification_invoice_number.py` passed |
| 6 | Invoices with control characters or newlines produce one `high`-severity finding with `reason="control_characters"` | Verified | `tests/test_verification_invoice_number.py` passed |
| 7 | Invoices with runaway length (> 64 characters) produce one `high`-severity finding with `reason="excessive_length"` | Verified | `tests/test_verification_invoice_number.py` passed |
| 8 | Invoices with absent (`None`) invoice number produce no finding (deferred to required-field completeness) | Verified | `tests/test_verification_invoice_number.py` passed |
| 9 | The check does not mutate the input extraction | Verified | `tests/test_verification_invoice_number.py` passed |
| 10 | `VerificationService.verify()` reports the finding and routes the verdict to `review_required` | Verified | `tests/test_verification_invoice_number.py` passed |
| 11 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | 1610 tests passed locally; quality gate green |

## Decision Log

### Decision 1: Enforce canonical placeholder and generic label dictionaries
- **Context:** OCR engines frequently read column headers (such as "INVOICE NUMBER" or "INV #") as the value when the actual identifier box is unaligned or blank, or transcribe template placeholder text (`N/A`, `NULL`, `SAMPLE`, `TBD`) when no number exists.
- **Decision:** Maintain immutable frozen canonical sets `_PLACEHOLDER_TOKENS` and `_GENERIC_LABEL_TOKENS` in `veridoc.verification.invoice_number` and categorize matched values cleanly with `reason="placeholder"` and `reason="generic_label"`.
- **Alternatives Considered:** Open-ended heuristics or LLM re-classification. Rejected: non-deterministic and ungrounded.
- **Blast Radius & Reversibility:** Pure function, zero impact on valid alphanumeric identifiers.

### Decision 2: Enforce strict structural hygiene (control characters, blank/punctuation, length)
- **Context:** OCR artifacts often include trailing line breaks or multiline blocks accidentally merged into the invoice number. Furthermore, runaway text (> 64 chars) or punctuation-only strings (`"-"`, `"---"`, `"."`) distort database indexes, downstream ERP ingestion, and human reviews.
- **Decision:** Check for non-printable control characters/newlines (`reason="control_characters"`), require at least one alphanumeric character (`reason="blank_or_punctuation"`), and enforce an upper length bound of `MAX_INVOICE_NUMBER_LENGTH = 64` (`reason="excessive_length"`).
- **Alternatives Considered:** Free-form string storage without validation. Rejected: leads to database index corruption and silent ERP integration failures.
- **Blast Radius & Reversibility:** Pure function; standard invoice numbers globally rarely exceed 35 characters, making 64 characters safely permissive.

### Decision 3: Assign `high` severity to `invalid_invoice_number` findings
- **Context:** An invoice without a valid, authentic identifier cannot be matched to purchase orders, reconciled against historical payments, or legally submitted for payment processing.
- **Decision:** Assign `high` severity to `invalid_invoice_number`, routing the invoice to `review_required` in `derive_verdict`.
- **Alternatives Considered:** `medium` or `low` severity. Rejected: invalid identifiers present immediate duplicate billing and reconciliation hazards, requiring human operator intervention.
- **Blast Radius & Reversibility:** Fully consistent with the verification severity framework.

## CI & Validation Log

Local commands run from the repository root on Windows with Python 3.12.12 and uv 0.9.13:

| Command | Result |
|---|---|
| `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` | Passed (zero whitespace issues) |
| `uv lock --check` | Passed |
| `uv run pip-audit` | Passed (0 known vulnerabilities; `veridoc` skipped as not on PyPI) |
| `uv run ruff check .` | Passed (All checks passed!) |
| `uv run ruff format --check .` | Passed (325 files formatted) |
| `uv run mypy` | Passed (124 source files) |
| `uv run pytest -q` | 1610 passed |
| `uv run pytest --cov=veridoc` | 1610 passed; 94.15% total branch coverage (90% floor) |
| `uv run pytest tests/test_documentation.py` | 3 passed |
| `uv build --clear` | Wheel and source distribution built |
| `uv run twine check dist/*` | Both distributions passed metadata validation |
| `uv run python scripts/check_distribution.py` | Both archives passed content and safety checks |
| Isolated wheel smoke test | Passed |
| Isolated source distribution smoke test | Passed |
