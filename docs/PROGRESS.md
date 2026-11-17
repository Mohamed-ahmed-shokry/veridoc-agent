# Phase 44 Progress Record: Extraction Evidence Grounding Verification

## Phase Overview

- **Phase:** Phase 44
- **Goal:** Implement deterministic verification of field-level and line-item-level `EvidenceReference` provenance when upstream extraction operates in evidence-grounded mode (ADR 0050), routing partially grounded extractions to `review_required`.
- **Status:** Complete
- **Branch:** `phase/evidence-grounding-verification`
- **Draft PR:** [#23](https://github.com/Mohamed-ahmed-shokry/veridoc-agent/pull/23)
- **Base:** `main`

## Task Status

| Step | Task | Status | Commit |
|---|---|---|---|
| 1 | Define Phase 44 specification in `docs/roadmap.md` | Completed | `4d7c40d` |
| 2 | Record ADR 0050 in `docs/decisions/0050-extraction-evidence-grounding-verification.md` | Completed | `88e68bf` |
| 3 | Register ADR 0050 in `docs/decisions/README.md` | Completed | `a5fdbb1` |
| 4 | Add `ungrounded_extracted_field` to `FindingType` in `src/veridoc/verification/models.py` | Completed | `b12eb04` |
| 5 | Add model acceptance test in `tests/test_verification_models.py` | Completed | `0f938d9` |
| 6 | Implement `REQUIRED_GROUNDED_HEADER_FIELDS` and `check_evidence_grounding` in `src/veridoc/verification/evidence_grounding.py` | Completed | `9956f34` |
| 7 | Add unit tests covering grounding, partial grounding, invalid spans, line items, and immutability in `tests/test_verification_evidence_grounding.py` | Completed | `7b1ee3a` |
| 8 | Register `test_verification_evidence_grounding` in `docs/testing.md` | Completed | `d59b3fd` |
| 9 | Integrate `check_evidence_grounding` into `VerificationService.verify()` | Completed | `c12cc48` |
| 10 | Add `VerificationService` integration and verdict tests in `tests/test_verification_evidence_grounding.py` | Completed | `b03e490` |
| 11 | Update documentation (`README.md`, `CHANGELOG.md`, `docs/architecture.md`, `AGENTS.md`) | Completed | `281d07b`, `d962cee`, `ac87baf`, `c72fe67` |
| 12 | Mark Phase 44 complete in `docs/roadmap.md` approval rule and phase table | Completed | `81c4b9b` |
| 13 | Record Phase 44 completion snapshot in `docs/release-evidence.md` | Completed | `cb502c3` |
| 14 | Finalize progress record with validation evidence | Completed | this commit |

## Acceptance Criteria

| # | Criterion | Status | Evidence |
|---|---|---|---|
| 1 | `ungrounded_extracted_field` is a valid `FindingType` literal union member | Verified | `tests/test_verification_models.py` passed (25 passed) |
| 2 | Evidence-free extraction (`evidence={}` and empty line-item evidence) emits `[]` | Verified | `tests/test_verification_evidence_grounding.py` passed |
| 3 | Fully grounded extraction emits `[]` | Verified | `tests/test_verification_evidence_grounding.py` passed |
| 4 | Missing critical header evidence emits `ungrounded_extracted_field` (`medium`) in fixed order | Verified | `tests/test_verification_evidence_grounding.py` passed |
| 5 | Absent (`None`) optional header fields do not require evidence | Verified | `tests/test_verification_evidence_grounding.py` passed |
| 6 | Ungrounded line items emit `ungrounded_extracted_field` (`medium`) in line-item order | Verified | `tests/test_verification_evidence_grounding.py` passed |
| 7 | Whitespace-only `text_span` or `page_number < 1` is rejected (`reason="invalid_evidence"`) | Verified | `tests/test_verification_evidence_grounding.py` passed |
| 8 | Input invoice extractions remain strictly immutable | Verified | `tests/test_verification_evidence_grounding.py` passed |
| 9 | `VerificationService.verify()` routes partially grounded invoices to `review_required` | Verified | `tests/test_verification_evidence_grounding.py` + end-to-end check passed |
| 10 | All local CI-parity checks and remote CI workflow runs pass 100% | Verified | Local CI parity green (1762 passed, 94.28% coverage); remote CI verified after push |

## Decision Log

### Decision 1: Activate grounding checks only when extraction provides evidence
- **Context:** Synthetic unit fixtures and non-grounding adapters omit `evidence` (`evidence={}` and `line_items[i].evidence=[]`). Requiring evidence unconditionally would break existing `clear` integration tests (`tests/test_processing_service.py`, `tests/test_review_retry_recovery_integration.py`).
- **Decision:** Return `[]` when `not invoice.evidence` and all line items have empty `evidence`; enforce grounding on `REQUIRED_GROUNDED_HEADER_FIELDS` and all line items whenever any evidence is present.
- **Alternatives Considered:** Unconditional grounding requirement. Rejected: incompatible with evidence-free adapters and existing test contracts.
- **Blast Radius & Reversibility:** Pure function in `veridoc.verification.evidence_grounding`.

### Decision 2: Reject whitespace-only `text_span` while allowing `text_span=None`
- **Context:** `page_image` references and some test `ocr_text` references legitimately set `text_span=None`, whereas a blank string `"   "` indicates an empty/corrupted citation.
- **Decision:** Accept `text_span is None` and require `bool(text_span.strip())` when `text_span is not None`.
- **Alternatives Considered:** Requiring non-empty `text_span` on all `ocr_text` references. Rejected: would break existing `tests/test_evaluation_runner.py` and `tests/test_evaluation_cli.py` fixtures.
- **Blast Radius & Reversibility:** Localized to `_is_valid_reference` helper.

## Validation & CI Log

- `git diff --check "$(git hash-object -t tree /dev/null)" HEAD`: Clean (0 errors)
- `uv lock --check`: Passed (Resolved 103 packages)
- `uv run pip-audit`: Passed (0 vulnerabilities; `veridoc` skipped)
- `uv run ruff check .`: Passed (All checks passed!)
- `uv run ruff format --check .`: Passed (338 files formatted)
- `uv run mypy`: Passed (0 issues across 128 source files)
- `uv run pytest --cov=veridoc`: Passed (1762 passed in 42.53s, 94.28% branch coverage, 90.0% floor)
- `uv run pytest tests/test_documentation.py`: Passed (3 passed)
- `uv build --clear`: Built `veridoc-0.1.0-py3-none-any.whl` and `veridoc-0.1.0.tar.gz`
- `uv run twine check dist/*`: Both distributions passed metadata validation
- `uv run python scripts/check_distribution.py`: Both archives passed content, entry-point, and path safety
- Isolated wheel smoke test: Passed
- Isolated sdist smoke test: Passed
