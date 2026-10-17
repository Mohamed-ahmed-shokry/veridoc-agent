# Phase 31 Progress Record: Document Type Verification

## Phase Overview

- **Phase:** Phase 31
- **Goal:** Introduce deterministic document type verification (ADR 0037) detecting non-invoice documents (`document_type != "invoice"`, including `"purchase_order"` and `"unknown"`), preventing unearned `clear` verdicts on non-invoice instruments.
- **Status:** In Progress
- **Branch:** `phase/document-type-verification`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Record ADR 0037 in `docs/decisions/` and index | Completed | `fbdf751`, `2bd94d4` |
| 2 | Define Phase 31 specification in `docs/roadmap.md` | Completed | `7f15f3f` |
| 3 | Initialize `docs/PROGRESS.md` for Phase 31 | In Progress | Pending |
| 4 | Add `unsupported_document_type` to `FindingType` in `src/veridoc/verification/models.py` | Pending | Pending |
| 5 | Add unit tests for `unsupported_document_type` in `tests/test_verification_models.py` | Pending | Pending |
| 6 | Implement `check_document_type` in `src/veridoc/verification/document_type.py` | Pending | Pending |
| 7 | Add unit tests in `tests/test_verification_document_type.py` covering invoice, PO, and unknown types | Pending | Pending |
| 8 | Integrate `check_document_type` into `VerificationService.verify()` | Pending | Pending |
| 9 | Add immutability, service integration, and verdict tests in `tests/test_verification_document_type.py` | Pending | Pending |
| 10 | Update `docs/testing.md` test inventory and guide | Pending | Pending |
| 11 | Update `docs/architecture.md`, `AGENTS.md`, and `README.md` | Pending | Pending |
| 12 | Update `CHANGELOG.md` for Phase 31 | Pending | Pending |
| 13 | Fix formatting and style across modified modules | Pending | Pending |
| 14 | Record Phase 31 completion snapshot in `docs/release-evidence.md` | Pending | Pending |
| 15 | Finalize `docs/PROGRESS.md` and verify full CI parity | Pending | Pending |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `unsupported_document_type` appears in `FindingType` and is accepted by `VerificationFinding` | Pending | Pending |
| 2 | `check_document_type` returns `[]` when `invoice.document_type == "invoice"` | Pending | Pending |
| 3 | `check_document_type` returns one `unsupported_document_type` finding (`severity="high"`) when `invoice.document_type == "purchase_order"` or `"unknown"` | Pending | Pending |
| 4 | `check_document_type` does not mutate input `InvoiceExtraction` | Pending | Pending |
| 5 | `VerificationService.verify()` includes findings and routes violating documents to `review_required` with `highest_severity="high"` | Pending | Pending |
| 6 | All local CI-parity checks and remote CI workflow runs pass 100% | Pending | Pending |

## Decision Log

### Decision 1: Scope of Phase 31 — Document Type Verification (ADR 0037)
- **Context:** `InvoiceExtraction` captures `document_type: Literal["invoice", "purchase_order", "unknown"]`, but `VerificationService` previously did not inspect it. Ingested purchase orders or unclassified documents (e.g. quotes, receipts, terms pages) could pass arithmetic and reference checks and receive an unearned `clear` invoice processing verdict.
- **Decision:** Establish `check_document_type(invoice)` returning `unsupported_document_type` (`severity="high"`) whenever `invoice.document_type != "invoice"`.
- **Alternatives Considered:** (a) Reject at ingestion/extraction boundary. Rejected: Breaks review console visibility into rejected or misclassified uploads. (b) Use `severity="medium"` for unknown documents. Rejected: Non-invoice instruments cannot be cleared for payment under any circumstance.
- **Blast Radius & Reversibility:** Zero breaking changes to existing models; purely additive verification check.

## Validation Results

Pending.

## Blockers

None.
