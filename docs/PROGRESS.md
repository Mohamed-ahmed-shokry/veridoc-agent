# Phase 31 Progress Record: Document Type Verification

## Phase Overview

- **Phase:** Phase 31
- **Goal:** Introduce deterministic document type verification (ADR 0037) detecting non-invoice documents (`document_type != "invoice"`, including `"purchase_order"` and `"unknown"`), preventing unearned `clear` verdicts on non-invoice instruments.
- **Status:** Complete
- **Branch:** `phase/document-type-verification`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Record ADR 0037 in `docs/decisions/` and index | Completed | `fbdf751`, `2bd94d4` |
| 2 | Define Phase 31 specification in `docs/roadmap.md` | Completed | `7f15f3f` |
| 3 | Initialize `docs/PROGRESS.md` for Phase 31 | Completed | `206ef82` |
| 4 | Add `unsupported_document_type` to `FindingType` in `src/veridoc/verification/models.py` | Completed | `f7450ff` |
| 5 | Add unit tests for `unsupported_document_type` in `tests/test_verification_models.py` | Completed | `56b841e` |
| 6 | Implement `check_document_type` in `src/veridoc/verification/document_type.py` | Completed | `6820e39` |
| 7 | Add unit tests in `tests/test_verification_document_type.py` covering invoice, PO, and unknown types | Completed | `91c9798` |
| 8 | Integrate `check_document_type` into `VerificationService.verify()` | Completed | `a309c2e` |
| 9 | Add immutability, service integration, and verdict tests in `tests/test_verification_document_type.py` | Completed | `d85f6a0`, `4c0ab4e` |
| 10 | Update `docs/testing.md` test inventory and guide | Completed | `de4f9bc` |
| 11 | Update `docs/architecture.md`, `AGENTS.md`, and `README.md` | Completed | `277c11b`, `8650c07`, `451c466` |
| 12 | Update `CHANGELOG.md` for Phase 31 | Completed | `e1809ec` |
| 13 | Record Phase 31 completion snapshot in `docs/release-evidence.md` | Completed | `69dfb9c` |
| 14 | Mark Phase 31 complete in `docs/roadmap.md` and update approval rule | Completed | `6327eab` |
| 15 | Finalize `docs/PROGRESS.md` and verify full CI parity | Completed | Pending |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `unsupported_document_type` appears in `FindingType` and is accepted by `VerificationFinding` | Verified | `tests/test_verification_models.py` passed |
| 2 | `check_document_type` returns `[]` when `invoice.document_type == "invoice"` | Verified | `tests/test_verification_document_type.py` passed |
| 3 | `check_document_type` returns one `unsupported_document_type` finding (`severity="high"`) when `invoice.document_type == "purchase_order"` or `"unknown"` | Verified | `tests/test_verification_document_type.py` passed |
| 4 | `check_document_type` does not mutate input `InvoiceExtraction` | Verified | `tests/test_verification_document_type.py` passed |
| 5 | `VerificationService.verify()` includes findings and routes violating documents to `review_required` with `highest_severity="high"` | Verified | `tests/test_verification_document_type.py` passed |
| 6 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | Ruff, mypy, pytest, pip-audit, twine, smoke tests pass |

## Decision Log

### Decision 1: Scope of Phase 31 — Document Type Verification (ADR 0037)
- **Context:** `InvoiceExtraction` captures `document_type: Literal["invoice", "purchase_order", "unknown"]`, but `VerificationService` previously did not inspect it. Ingested purchase orders or unclassified documents (e.g. quotes, receipts, terms pages) could pass arithmetic and reference checks and receive an unearned `clear` invoice processing verdict.
- **Decision:** Establish `check_document_type(invoice)` returning `unsupported_document_type` (`severity="high"`) whenever `invoice.document_type != "invoice"`.
- **Alternatives Considered:** (a) Reject at ingestion/extraction boundary. Rejected: Breaks review console visibility into rejected or misclassified uploads. (b) Use `severity="medium"` for unknown documents. Rejected: Non-invoice instruments cannot be cleared for payment under any circumstance.
- **Blast Radius & Reversibility:** Zero breaking changes to existing models; purely additive verification check.

## Validation Results

- Tracked whitespace check: `git diff --check "$(git hash-object -t tree /dev/null)" HEAD` passed (exit code 0).
- Linter & Formatter: `ruff check .` and `ruff format --check .` passed cleanly.
- Type Checker: `mypy` passed with 0 errors across all source files.
- Test suite: All unit and integration tests passing, branch coverage >= 90% floor.
- Documentation tests: Markdown links, documented test-module inventory, and tracked whitespace hygiene test passed.
- Vulnerability Audit: `pip-audit` passed with 0 vulnerabilities found.
- Distribution Build & Twine: `uv build --clear` and `twine check dist/*` passed.
- Distribution Smoke Tests: isolated wheel and sdist smoke tests passed.

## Blockers

None.
