# 0038: Extraction uncertainty verification

## Status

Accepted

## Context

In Veridoc's document-intelligence pipeline, extraction is the initial stage where OCR text
and document images are converted into structured `InvoiceExtraction` models. The structured
schema explicitly includes `uncertainties: list[ExtractionUncertainty] = Field(default_factory=list)`,
where each `ExtractionUncertainty` captures an optional `field: str | None` and a mandatory
`reason: str`. Extraction models (e.g. OpenAI Responses API) are prompted to adhere to a strict
rule: "If a field is not present or cannot be determined with certainty, leave it null or
unknown. Record ambiguities in uncertainties."

However, prior to Phase 32, `VerificationService` did not inspect `invoice.uncertainties`.
An invoice could have explicit extraction ambiguities declared by the model—such as watermarks
partially obscuring invoice totals, tears in the document cutting through issue dates, ambiguous
handwriting on unit prices, or unreadable tax percentages. If the visible or defaulted figures
satisfied deterministic arithmetic and reference checks, the invoice bypassed human review
and received an unearned `clear` processing verdict.

Allowing invoices with declared extraction uncertainties to clear automated reconciliation introduces
grave financial and audit hazards:
1. **False Straight-Through Processing**:
   Accounts payable automation relies on the guarantee that `clear` invoices require no human
   intervention. If extraction uncertainty is ignored, corrupted or partially guessed data is
   posted directly to financial ledgers without human validation.
2. **Breach of the Document-Intelligence Contract**:
   Veridoc is designed specifically to decide whether data extracted from invoices can be trusted.
   When the extraction stage explicitly reports that certain facts are ambiguous or unverifiable,
   ignoring that declaration subverts the system's foundational purpose.
3. **Audit Trail Blindspot**:
   Downstream auditors and AP managers cannot easily distinguish between high-confidence
   extractions and extractions where the AI explicitly flagged perceptual doubts unless those doubts
   are elevated into first-class verification findings.

Establishing a deterministic check over `invoice.uncertainties` ensures that any invoice with
declared extraction ambiguities is immediately flagged with `severity="medium"`, routing the
document to mandatory human review (`review_required`).

## Decision

Phase 32 introduces:

1. **`extraction_uncertainty` finding type**:
   - Added to `FindingType` in `veridoc.verification.models`.
   - Comparison source: `"invoice_fields"`.
   - Deterministic rule: `"len(invoice.uncertainties) == 0"`.
   - Severity: `"medium"`.
   - Observed value: `uncertainty.reason`.
   - Expected value: `None`.
   - Structured details include:
     `"field"`, `"reason"`, and `"uncertainty_index"`.

2. **Exclusion Paths (Pure Function Safety)**:
   - Returns `[]` when `invoice.uncertainties` is empty.

3. **Triggering Paths**:
   - Returns one `extraction_uncertainty` finding (`severity="medium"`) for each entry in
     `invoice.uncertainties`, preserving list order.
   - When `uncertainty.field` is present:
     `explanation=f"Extraction uncertainty declared for field '{uncertainty.field}': {uncertainty.reason}"`.
   - When `uncertainty.field` is None:
     `explanation=f"General extraction uncertainty declared: {uncertainty.reason}"`.

4. **Pure Function and Service Integration**:
   - Implemented in `veridoc.verification.uncertainties.check_extraction_uncertainties(invoice)`.
   - Integrated into `VerificationService.verify()`, routing any invoice with declared extraction
     uncertainties to `review_required`.

## Alternatives Considered

1. **Use `severity="high"` for all extraction uncertainties**:
   - *Rejected*: `severity="high"` is reserved for hard fraud indicators (e.g. vendor bank account
     mismatches, negative totals, post-dated invoices, unsupported document types). `severity="medium"`
     is standard for date and field ambiguities and successfully enforces the `review_required` verdict.
2. **Discard uncertainties at extraction time and rely solely on arithmetic mismatches**:
   - *Rejected*: Many extraction errors still balance arithmetically (e.g. an ambiguous single total
     with no subtotal/tax breakdown). Explicit uncertainty declarations provide direct evidence of
     untrustworthy data that arithmetic cannot detect.
3. **Filter uncertainties by field name**:
   - *Rejected*: Any ambiguity declared on any field (or the document as a whole) warrants reviewer
     inspection before automated straight-through processing.

## Consequences

- Invoices with declared extraction uncertainties cannot receive an unearned `clear` processing verdict.
- Every uncertainty declared by the upstream extractor is elevated to an accountable, evidence-backed
  verification finding visible in the review console and auditor evidence exports.
- Strictly adheres to the pure, deterministic verification architecture and preserves input immutability.
