# 0045: Invoice number format and placeholder verification

## Status

Accepted

## Context

In accounts payable (AP) automation, enterprise resource planning (ERP) integration, and financial
audit reconciliation, `invoice_number` is the foundational vendor-scoped transaction identity. It is
critical for three-way matching against purchase orders, remittance tracking, input tax deduction
reporting, and preventing duplicate payment disbursements.

In Phase 33 (ADR 0039), `check_required_fields` mandated the presence of `invoice_number` with
`high` severity. However, that check only evaluates whether `invoice.invoice_number is not None`.
Because `InvoiceExtraction.invoice_number` is typed as `str | None`, non-null strings that carry no
genuine billing identity easily pass required field completeness.

In real-world document processing, multimodal vision/OCR extraction pipelines frequently produce
corrupted or non-identifying invoice number values:
1. **Generic Placeholders**: Extractors transcribe `"N/A"`, `"NA"`, `"NONE"`, `"NULL"`, `"NIL"`,
   `"UNKNOWN"`, `"TBD"`, `"PENDING"`, `"VOID"`, `"SAMPLE"`, `"TEST"`, or `"UNDEFINED"` when an
   identifier is absent on the source visual.
2. **Field Labels Extracted as Values**: Models transcribe the printed header label itself—such as
   `"INVOICE"`, `"INVOICE NUMBER"`, `"INVOICE NO"`, `"INV#"`, `"BILL NO"`, or `"NUMBER"`—when visual
   alignment fails.
3. **Blank or Punctuation-Only Strings**: Vision models transcribe dashes, hyphens, slashes, or
   periods (`"-"`, `"---"`, `"/"`, `"."`, `"--"`) or whitespace-only strings (`"   "`).
4. **Control Characters & Multi-line Spans**: Text blocks containing embedded newlines (`\n`, `\r`)
   or unprintable control characters accidentally captured from tabular OCR regions.
5. **Runaway OCR Paragraphs**: Unbounded text dumps where OCR captures a sentence or address block
   into the invoice number field (exceeding standard length bounds).

Allowing these corrupted values to receive an unearned `clear` processing verdict introduces severe
financial and operational hazards:
- **Ledger Corruption**: Posting placeholder strings like `"N/A"` or `"INVOICE"` into ERP systems
  creates invalid master records.
- **Defeated Duplicate Detection**: When multiple distinct invoices from a vendor carry `"N/A"`,
  either duplicate invoice detection produces false alarms or subsequent genuine invoices are blocked.
- **Failed Payment Remittance**: Banking and ACH payment networks reject payment files referencing
  blank, punctuation-only, or multi-line invoice identifiers.

Establishing a deterministic verification rule for invoice number syntax, length, and placeholder
detection ensures that any invoice with an invalid identifier is flagged with `high` severity, routing
it to mandatory human review (`review_required`).

## Decision

Phase 39 introduces:

1. **`invalid_invoice_number` finding type**:
   - Added to `FindingType` in `veridoc.verification.models`.
   - Comparison source: `"invoice_fields"`.
   - Severity: `"high"`.
   - Deterministic rule: `"invoice.invoice_number is a valid alphanumeric identifier and not a placeholder"`.
   - Structured details include:
     `"field": "invoice_number"`, `"invoice_number"`, and `"reason"`.

2. **Categorized invalidity reasons**:
   - `"placeholder"`: Exact case-insensitive match against canonical placeholder tokens (`n/a`, `na`,
     `none`, `null`, `nil`, `unknown`, `tbd`, `pending`, `void`, `sample`, `test`, `undefined`).
   - `"generic_label"`: Case-insensitive match against generic field labels (`invoice`,
     `invoice number`, `invoice no`, `invoice #`, `inv`, `inv no`, `inv #`, `bill`, `bill no`,
     `bill #`, `number`, `no`, `#`).
   - `"blank_or_punctuation"`: The string is empty, whitespace-only, or contains zero alphanumeric
     characters.
   - `"control_characters"`: The string contains newlines (`\n`, `\r`), tabs, or unprintable control
     characters.
   - `"excessive_length"`: The string length exceeds `MAX_INVOICE_NUMBER_LENGTH = 64` characters.

3. **Exclusion paths (pure function safety)**:
   - Returns `[]` when `invoice.invoice_number is None` (deferred to Phase 33 required-field completeness).
   - Returns `[]` when `invoice.invoice_number` is a valid alphanumeric identifier (e.g. `INV-2026-001`,
     `987654`, `A/102-B`, `REC-009`).

4. **Input immutability**:
   - Pure function that never mutates the input extraction.

5. **Service integration**:
   - Integrated into `VerificationService.verify()`, routing any finding to `review_required`.

## Consequences

- Invoices with placeholder numbers, generic labels, or runaway text dumps are deterministically
  intercepted before ledger posting.
- Standard commercial alphanumeric invoice number formats pass with zero false positives.
