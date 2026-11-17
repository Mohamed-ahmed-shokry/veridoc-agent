# 0050: Extraction evidence grounding verification

## Status

Accepted

## Context

Veridoc's `InvoiceExtraction` schema records field-level provenance in `evidence: dict[str, list[EvidenceReference]]` and per-line provenance in `InvoiceLineItem.evidence: list[EvidenceReference]`. Each `EvidenceReference` captures `page_number >= 1`, `source` (`"ocr_text"` or `"page_image"`), and an optional `text_span`.

In multimodal LLM/VLM extraction pipelines, a common failure mode is **partial grounding**: the extractor supplies valid `EvidenceReference` citations for some fields (for example `vendor_name` or `invoice_number`), while omitting provenance for other populated critical header fields (`total`, `invoice_date`, `currency`) or line items—often indicating an ungrounded guess or hallucination.

Prior to Phase 44, `VerificationService` never checked `invoice.evidence` or `line_item.evidence`, allowing partially grounded extractions to clear automated verification whenever arithmetic and format checks passed.

## Decision

1. **Evidence-Grounded Mode Activation**: When an extraction provides no evidence anywhere (`not invoice.evidence` and `all(not item.evidence for item in invoice.line_items)`), `check_evidence_grounding` returns `[]`. This preserves full backward compatibility with evidence-free synthetic fixtures and non-grounding adapters.
2. **Critical Header Field Grounding**: When any evidence is present on the extraction, every populated field in `REQUIRED_GROUNDED_HEADER_FIELDS = ("invoice_number", "invoice_date", "currency", "total")` must have at least one valid `EvidenceReference` in `invoice.evidence.get(field, [])`.
3. **Line-Item Grounding**: When any evidence is present on the extraction, every `InvoiceLineItem` in `invoice.line_items` must carry at least one valid `EvidenceReference` in `item.evidence`.
4. **Valid Evidence Predicate**: An `EvidenceReference` is valid if `ev.page_number >= 1` and, when `ev.text_span is not None`, `bool(ev.text_span.strip())` (rejecting blank/whitespace-only text spans).
5. **Finding Contract**: Missing or invalid grounding emits `ungrounded_extracted_field` (`severity="medium"`) with `comparison_source="invoice_fields"` for header fields and `comparison_source="invoice_line_items"` for line items, routing partially grounded extractions to `review_required`.

## Consequences

- **Positive**: Hallucinated or ungrounded critical fields and line items in evidence-reporting pipelines are deterministically flagged for human review.
- **Neutral**: Evidence-free fixtures and non-grounding adapters continue to behave identically.
- **Negative**: None; pure deterministic check with zero side effects.
