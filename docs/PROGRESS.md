# Phase 43 Progress Record: OCR and Extraction Confidence Threshold Verification

## Phase Overview

- **Phase:** Phase 43
- **Goal:** Implement deterministic verification of upstream `ocr_confidence` and `extraction_confidence` scores against configurable minimum confidence thresholds (ADR 0049) so degraded scans and low-confidence extractions cannot receive an unearned `clear` verdict.
- **Status:** Complete
- **Branch:** `phase/confidence-threshold-verification`
- **Draft PR:** [#22](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/pull/22)
- **Base:** `main`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 43 specification in `docs/roadmap.md` | Completed | `c611470` |
| 2 | Record ADR 0049 in `docs/decisions/0049-ocr-and-extraction-confidence-verification.md` | Completed | `d6207ee` |
| 3 | Register ADR 0049 in `docs/decisions/README.md` | Completed | `8e9adec` |
| 4 | Add `low_ocr_confidence` and `low_extraction_confidence` to `FindingType` in `src/veridoc/verification/models.py` | Completed | `d63dffb` |
| 5 | Add model acceptance tests in `tests/test_verification_models.py` | Completed | `6ebeae3` |
| 6 | Implement `check_confidence_thresholds` and constants in `src/veridoc/verification/confidence.py` | Completed | `e631152` |
| 7 | Add unit tests covering threshold, boundary, custom-threshold, and immutability paths in `tests/test_verification_confidence.py` | Completed | `88b402f` |
| 8 | Register `test_verification_confidence` in `docs/testing.md` | Completed | `2c62485` |
| 9 | Integrate `check_confidence_thresholds` into `VerificationService.verify()` | Completed | `55afecb` |
| 10 | Add `VerificationService` integration and verdict tests in `tests/test_verification_confidence.py` | Completed | `c166d0f` |
| 11 | Update documentation (`README.md`, `CHANGELOG.md`, `docs/architecture.md`, `AGENTS.md`) | Completed | `07e9975`, `9c9187b`, `db31b9b`, `46c0b02` |
| 12 | Mark Phase 43 complete in `docs/roadmap.md` approval rule and phase table | Completed | `c40e11a` |
| 13 | Record Phase 43 completion snapshot in `docs/release-evidence.md` | Completed | `d7dca0b` |
| 14 | Finalize progress record with validation evidence | Completed | this commit |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `low_ocr_confidence` and `low_extraction_confidence` are valid `FindingType` literal union members | Verified | `tests/test_verification_models.py` passed (24 passed) |
| 2 | When both confidence fields are `None`, zero findings are emitted | Verified | `tests/test_verification_confidence.py` passed |
| 3 | When confidence scores meet or exceed `70.0`, zero findings are emitted | Verified | `tests/test_verification_confidence.py` passed |
| 4 | When `ocr_confidence < 70.0`, emits `low_ocr_confidence` (`severity="medium"`) with structured details | Verified | `tests/test_verification_confidence.py` passed |
| 5 | When `extraction_confidence < 70.0`, emits `low_extraction_confidence` (`severity="medium"`) with structured details | Verified | `tests/test_verification_confidence.py` passed |
| 6 | When both are below threshold, emits `low_ocr_confidence` before `low_extraction_confidence` | Verified | `tests/test_verification_confidence.py` passed |
| 7 | Custom thresholds are respected and invalid thresholds raise `ValueError` | Verified | `tests/test_verification_confidence.py` passed |
| 8 | Input invoice extractions remain strictly immutable | Verified | `tests/test_verification_confidence.py` passed |
| 9 | `VerificationService.verify()` runs check and routes low-confidence invoices to `review_required` | Verified | `tests/test_verification_confidence.py` + end-to-end check passed |
| 10 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | Local CI parity green (1745 passed, 94.25% coverage); remote CI verified after push |

## Decision Log

### Decision 1: Separate finding types for OCR vs. extraction confidence
- **Context:** `InvoiceExtraction` carries both `ocr_confidence` (OCR scan quality) and `extraction_confidence` (structured extractor certainty).
- **Decision:** Add two distinct `FindingType` values: `low_ocr_confidence` and `low_extraction_confidence`.
- **Alternatives Considered:** A single generic `low_confidence` finding. Rejected: separating them lets operators immediately tell whether to re-scan the physical document or manually inspect field parsing.
- **Blast Radius & Reversibility:** Pure additive change in `FindingType` and `veridoc.verification.confidence`.

### Decision 2: Default threshold of 70.0% and medium severity
- **Context:** Confidence fields are optional (`None` when omitted) and bounded `[0, 100]`.
- **Decision:** Use `DEFAULT_MIN_OCR_CONFIDENCE = 70.0` and `DEFAULT_MIN_EXTRACTION_CONFIDENCE = 70.0`, emitting `severity="medium"` when `confidence < threshold` and `[]` when `confidence is None`.
- **Alternatives Considered:** Rejecting `None` confidence or using `high` severity. Rejected: many adapters and test fixtures omit confidence (`None`), and `medium` severity already routes to `review_required` while preserving `high` for direct financial/fraud contradictions.
- **Blast Radius & Reversibility:** Thresholds are keyword arguments with default constants; trivial to tune.

## Validation & CI Log

- `git diff --check "$(git hash-object -t tree /dev/null)" HEAD`: Clean (0 errors)
- `uv lock --check`: Passed (Resolved 103 packages)
- `uv run pip-audit`: Passed (0 vulnerabilities; `veridoc` skipped)
- `uv run ruff check .`: Passed (All checks passed!)
- `uv run ruff format --check .`: Passed (335 files formatted)
- `uv run mypy`: Passed (0 issues across 127 source files)
- `uv run pytest --cov=veridoc`: Passed (1745 passed in 52.60s, 94.25% branch coverage, 90.0% floor)
- `uv run pytest tests/test_documentation.py`: Passed (3 passed)
- `uv build --clear`: Built `veridoc-0.1.0-py3-none-any.whl` and `veridoc-0.1.0.tar.gz`
- `uv run twine check dist/*`: Both distributions passed metadata validation
- `uv run python scripts/check_distribution.py`: Both archives passed content, entry-point, and path safety
- Isolated wheel smoke test: Passed
- Isolated sdist smoke test: Passed
