# Phase 32 Progress Record: Extraction Uncertainty Verification

## Phase Overview

- **Phase:** Phase 32
- **Goal:** Introduce deterministic extraction uncertainty verification (ADR 0038) detecting declared extraction ambiguities (`len(invoice.uncertainties) > 0`), preventing unearned `clear` verdicts when upstream extraction explicitly declares that extracted fields or the document could not be determined with certainty.
- **Status:** Complete
- **Branch:** `phase/extraction-uncertainty-verification`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Record ADR 0038 in `docs/decisions/` and index | Completed | `55a079f`, `b5fe1c9` |
| 2 | Define Phase 32 specification in `docs/roadmap.md` | Completed | `c0230af` |
| 3 | Initialize `docs/PROGRESS.md` for Phase 32 | Completed | `49b02f1` |
| 4 | Add `extraction_uncertainty` to `FindingType` in `src/veridoc/verification/models.py` | Completed | `2c63594` |
| 5 | Add unit tests for `extraction_uncertainty` in `tests/test_verification_models.py` | Completed | `5ac1ca7` |
| 6 | Implement `check_extraction_uncertainties` in `src/veridoc/verification/uncertainties.py` | Completed | `c2f9be8` |
| 7 | Add unit tests for `check_extraction_uncertainties` in `tests/test_verification_uncertainties.py` | Completed | `bc0577b` |
| 8 | Integrate `check_extraction_uncertainties` into `VerificationService.verify()` | Completed | `3eab5df` |
| 9 | Add immutability, service integration, and verdict tests in `tests/test_verification_uncertainties.py` | Completed | `0898f22` |
| 10 | Update `docs/testing.md` test inventory and guide | Completed | `65a889c` |
| 11 | Update `docs/architecture.md`, `AGENTS.md`, and `README.md` | Completed | `de8230d`, `f5bf603`, `9579da2` |
| 12 | Update `CHANGELOG.md` for Phase 32 | Completed | `2e5c182` |
| 13 | Record Phase 32 completion snapshot in `docs/release-evidence.md` | Completed | `ccea9a2` |
| 14 | Mark Phase 32 complete in `docs/roadmap.md` and update approval rule | Completed | `e24b071` |
| 15 | Finalize `docs/PROGRESS.md` and verify full CI parity | Completed | Pending |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `extraction_uncertainty` appears in `FindingType` and is accepted by `VerificationFinding` | Verified | `tests/test_verification_models.py` passed |
| 2 | `check_extraction_uncertainties` returns `[]` when `invoice.uncertainties` is empty | Verified | `tests/test_verification_uncertainties.py` passed |
| 3 | `check_extraction_uncertainties` returns one `extraction_uncertainty` finding (`severity="medium"`) for each declared uncertainty in `invoice.uncertainties` | Verified | `tests/test_verification_uncertainties.py` passed |
| 4 | `check_extraction_uncertainties` does not mutate input `InvoiceExtraction` | Verified | `tests/test_verification_uncertainties.py` passed |
| 5 | `VerificationService.verify()` includes `extraction_uncertainty` findings and routes violating documents to `review_required` | Verified | `tests/test_verification_uncertainties.py` passed |
| 6 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | Ruff, mypy, pytest, pip-audit, twine, smoke tests pass |

## Decision Log

### Decision 1: Scope of Phase 32 — Extraction Uncertainty Verification (ADR 0038)
- **Context:** `InvoiceExtraction` models capture `uncertainties: list[ExtractionUncertainty]`, instructing extraction models to declare any perceptual or textual ambiguities (e.g., watermarks, tears, blurry fields). Prior to Phase 32, `VerificationService` ignored `invoice.uncertainties`, allowing invoices with known ambiguities to pass arithmetic/reference rules and receive an unearned `clear` verdict.
- **Decision:** Establish `check_extraction_uncertainties(invoice)` returning one `extraction_uncertainty` finding (`severity="medium"`) for each declared uncertainty, routing the invoice to `review_required`.
- **Alternatives Considered:** (a) Use `severity="high"`. Rejected: `high` is reserved for confirmed fraud or critical invariant violations (e.g. bank account mismatch, negative total). `medium` is the standard for field-level ambiguity requiring review. (b) Discard uncertainties at extraction time. Rejected: Direct evidence of untrustworthy data would be lost. (c) Filter uncertainties by field name. Rejected: Any uncertainty on any field or the document warrants review before straight-through processing.
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
