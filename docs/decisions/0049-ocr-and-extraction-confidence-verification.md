# 0049: OCR and extraction confidence threshold verification

## Status

Accepted

## Context

Veridoc's `InvoiceExtraction` schema captures two upstream percentage confidence scores (bounded `[0, 100]`):
1. `ocr_confidence`: Mean document-level optical character recognition confidence computed by the OCR boundary (`veridoc.ocr.service` / `veridoc.ocr.tesseract`).
2. `extraction_confidence`: Structured extraction confidence reported by the extraction provider (`veridoc.extraction`).

Prior to Phase 43, `VerificationService` never evaluated either confidence score. Whenever a physically degraded, blurry, low-DPI, or skewed invoice scan produced a low `ocr_confidence` (e.g., `32.0`) or an ambiguous document yielded a low `extraction_confidence` (e.g., `40.0`), the extracted fields could still pass deterministic arithmetic, format, and date checks—receiving an unearned `clear` processing verdict without human review.

Establishing deterministic confidence-threshold verification ensures that low-confidence extractions are surfaced as first-class verification findings and routed to `review_required`.

## Decision

1. **Two Distinct Finding Types**: Add `low_ocr_confidence` and `low_extraction_confidence` to `FindingType` in `veridoc.verification.models` so reviewers and downstream audit trails can immediately distinguish scan/OCR quality issues from structured-extraction model uncertainty.
2. **Default Thresholds**: Define `DEFAULT_MIN_OCR_CONFIDENCE: Final[float] = 70.0` and `DEFAULT_MIN_EXTRACTION_CONFIDENCE: Final[float] = 70.0` in `veridoc.verification.confidence`. Scores strictly below their respective threshold (`confidence < threshold`) trigger a finding; scores at or above the threshold (`confidence >= threshold`) pass.
3. **Optional Field Passthrough**: When `ocr_confidence` or `extraction_confidence` is `None` (e.g., omitted by an upstream adapter or synthetic test fixture), no finding is emitted for that field.
4. **Severity & Ordering**: Both findings emit with `severity="medium"`, `comparison_source="invoice_fields"`, and structured `details` (`field`, `confidence`, `threshold`). When both scores are below threshold, `low_ocr_confidence` is emitted before `low_extraction_confidence`.
5. **Pure Rule & Service Integration**: Implement `check_confidence_thresholds(invoice, min_ocr_confidence=DEFAULT_MIN_OCR_CONFIDENCE, min_extraction_confidence=DEFAULT_MIN_EXTRACTION_CONFIDENCE)` in `veridoc.verification.confidence` and invoke it in `VerificationService.verify()`.

## Consequences

- **Positive**: Degraded scans and low-confidence extractions can no longer silently achieve `clear` verdicts; operators receive clear, actionable findings with exact observed confidence vs. threshold.
- **Neutral**: Existing test fixtures and adapters that omit confidence scores (`None`) or provide high confidence (`>= 70.0`) remain unaffected.
- **Negative**: None; thresholds are parameterized for callers that require stricter or looser operational bounds.
