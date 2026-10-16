# Phase 28 Progress Record: Payment Terms Due Date Consistency Verification

## Phase Overview

- **Phase:** Phase 28
- **Goal:** Implement deterministic payment terms and due date consistency verification (`payment_terms_due_date_mismatch` in `veridoc.verification.payment_terms`) to detect predatory term acceleration and due date calculation or extraction errors.
- **Status:** Complete
- **Branch:** `phase/payment-terms-due-date`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 28 in `docs/roadmap.md` | Completed | `f453706` |
| 2 | Record ADR 0035 in `docs/decisions/` and register in `docs/decisions/README.md` | Completed | `f12077d` |
| 3 | Initialize Phase 28 progress record and decision log in `docs/PROGRESS.md` | Completed | `a2fa0f3` |
| 4 | Add `payment_terms_due_date_mismatch` to `FindingType` in `src/veridoc/verification/models.py` | Completed | `5931bb8` |
| 5 | Add `payment_terms_due_date_mismatch` model test in `tests/test_verification_models.py` | Completed | `c419739` |
| 6 | Implement `parse_payment_terms_days` in `src/veridoc/verification/payment_terms.py` | Completed | `d27a7be` |
| 7 | Add unit tests for `parse_payment_terms_days` in `tests/test_verification_payment_terms.py` | Completed | `d27a7be` |
| 8 | Implement `check_payment_terms_due_date` in `src/veridoc/verification/payment_terms.py` | Completed | `d27a7be` |
| 9 | Add unit tests for `check_payment_terms_due_date` in `tests/test_verification_payment_terms.py` | Completed | `d27a7be` |
| 10 | Integrate `check_payment_terms_due_date` into `VerificationService.verify()` | Completed | `15b2490` |
| 11 | Add `VerificationService`, immutability, and verdict tests in `tests/test_verification_payment_terms.py` | Completed | `15b2490` |
| 12 | Update `docs/architecture.md` and `docs/testing.md` for Phase 28 | Completed | `84c4e76` |
| 13 | Update `AGENTS.md`, `README.md`, and `CHANGELOG.md` for Phase 28 | Completed | `47f7dc8`, `18f0ad1` |
| 14 | Record release evidence in `docs/release-evidence.md` and finalize `docs/PROGRESS.md` | Completed | `current` |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `payment_terms_due_date_mismatch` appears in `FindingType` and is accepted by `VerificationFinding` | Verified | `tests/test_verification_models.py` passed |
| 2 | `parse_payment_terms_days` correctly parses Net terms, cash discount net terms, and immediate terms, returning `None` for unparseable terms | Verified | `tests/test_verification_payment_terms.py` passed (18/18) |
| 3 | `check_payment_terms_due_date` returns `[]` when fields are missing, unparseable, matching, or have valid weekend rolls | Verified | `tests/test_verification_payment_terms.py` passed |
| 4 | `check_payment_terms_due_date` returns `high` severity for accelerated due dates and `medium` severity for extended due dates | Verified | `tests/test_verification_payment_terms.py` passed |
| 5 | `VerificationService.verify()` includes payment terms due date findings and routes non-conforming invoices to `review_required` | Verified | `tests/test_verification_payment_terms.py` passed |
| 6 | Full quality gate passes without regression | Verified | 1335 passed, 93.92% coverage, all gates passed |

## Decision Log

### Decision 1: Scope of Phase 28 — Payment Terms Due Date Consistency Verification
- **Context:** In commercial invoices, `payment_terms` defines the contractually binding credit window between `invoice_date` and `due_date`. Previously, `check_invoice_dates` only verified `invoice_date <= due_date`, and `check_payment_terms` only verified historical consistency against prior vendor invoices. An invoice with `payment_terms="Net 30"` and `due_date` only 3 days after issue cleared verification without review. Vendors sometimes artificially shorten due dates to induce premature payment (predatory term acceleration), or buggy invoicing systems generate erroneous due dates.
- **Decision:** Implement pure deterministic functions in `veridoc.verification.payment_terms`:
  1. `parse_payment_terms_days(terms)`: parses standard terms (`Net <N>`, cash discount `<D>/<T> Net <N>`, `Due on receipt`/`Immediate`), returning `None` for unrecognized terms.
  2. Weekend business-day roll: if `expected_due_date` lands on Saturday (+2 days to Monday) or Sunday (+1 day to Monday), accept Monday as consistent.
  3. `check_payment_terms_due_date(invoice)`: emits `payment_terms_due_date_mismatch` with `severity="high"` if accelerated (`due_date < expected_due_date`) and `severity="medium"` if extended (`due_date > expected_due_date`).
- **Alternatives Considered:**
  1. *Fuzzy-parse arbitrary free-form terms.* Rejected: In deterministic financial verification, false positives from guessing ambiguous natural language terms are dangerous. Safe fallback to `None` guarantees zero false positives on non-standard agreements.
  2. *Treat weekend due dates strictly as mismatches.* Rejected: Many ERPs automatically roll weekend maturity dates to the next business day (Monday). Supporting weekend rolls prevents false positives on standard accounting software output.
- **Blast Radius & Reversibility:** Pure deterministic verification rule with no database migrations, no API schema changes, and full backward compatibility.

## Validation Results

- Baseline suite: 1316 tests passing.
- Phase 28 final suite: 1335 tests passing, 0 failures, 93.92% branch coverage. All 18 payment terms consistency tests passing.

## Blockers

None.
