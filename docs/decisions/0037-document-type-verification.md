# 0037: Document type verification

## Status

Accepted

## Context

In commercial accounts payable (AP) workflows, documents submitted for invoice processing
must be genuine payable invoices. Veridoc's structured extraction boundary defines
`document_type: DocumentType = Literal["invoice", "purchase_order", "unknown"]`, instructing
vision and language models to classify ingested documents based on document structure,
headings, and semantics.

However, prior to Phase 31, `VerificationService` did not inspect `invoice.document_type`.
Instead, any extracted document entering the deterministic verification pipeline was evaluated
as an invoice. If an operator or upstream workflow mistakenly uploaded a purchase order
(such as an internal PO or a vendor's copy of a purchase order) or an unidentifiable document
(such as a quote, packing slip, receipt, or marketing material classified as `unknown`),
the verification pipeline evaluated arithmetic and reference data without checking document
classification. If arithmetic fields balanced and reference data produced no conflicting
signals, non-invoice documents could receive an unearned `clear` processing verdict.

Allowing non-invoice documents (specifically purchase orders or unknown documents) to clear
invoice verification introduces severe financial and operational hazards:
1. **Purchase Order Inversion & Duplicate Payment**:
   Internal purchase orders are authorizations to buy, not demands for payment. Treating a
   purchase order as an invoice can lead to unauthorized disbursement or double-paying when
   the actual invoice arrives later.
2. **Non-Invoice Document Pollution**:
   Quotes, pro-forma estimates, and non-commercial documents entering AP ledgers distort
   accrual balances, generate false liabilities, and waste human review time downstream.
3. **Extraction Classifier Neglect**:
   Extraction models provide explicit document classification (`document_type`), but failing
   to verify this fact deterministically invalidates the document intelligence boundary.

Establishing an explicit, deterministic document type check ensures that only genuine
invoices (`document_type == "invoice"`) can clear automated processing, while all non-invoice
documents are immediately flagged with high severity for human review.

## Decision

Phase 31 introduces:

1. **`unsupported_document_type` finding type**:
   - Added to `FindingType` in `veridoc.verification.models`.
   - Comparison source: `"invoice_fields"`.
   - Deterministic rule: `"document_type == 'invoice'"`.
   - Severity: `"high"`.
   - Structured details include:
     `"document_type"`.

2. **Exclusion Paths (Pure Function Safety)**:
   - Returns `[]` when `invoice.document_type == "invoice"`.

3. **Triggering Paths**:
   - When `invoice.document_type == "purchase_order"`, returns one `unsupported_document_type`
     finding with `severity="high"`, `explanation="The extracted document is classified as a purchase order, not an invoice."`,
     `observed_value="purchase_order"`, `expected_value="invoice"`.
   - When `invoice.document_type == "unknown"`, returns one `unsupported_document_type`
     finding with `severity="high"`, `explanation="The extracted document could not be identified as an invoice."`,
     `observed_value="unknown"`, `expected_value="invoice"`.
   - When `invoice.document_type` has any other non-invoice value, returns one `unsupported_document_type`
     finding with `severity="high"`, `explanation=f"The extracted document type '{invoice.document_type}' is not supported as an invoice."`,
     `observed_value=str(invoice.document_type)`, `expected_value="invoice"`.

4. **Pure Function and Service Integration**:
   - Implemented in `veridoc.verification.document_type.check_document_type(invoice)`.
   - Integrated into `VerificationService.verify()`, routing violating non-invoice documents to `review_required` with `highest_severity="high"`.

## Alternatives Considered

1. **Reject non-invoice documents at the ingestion/extraction boundary**:
   - *Rejected*: Ingestion and extraction are meant to capture and extract document facts without making irreversible verification decisions. Downstream reviewers need the extracted snapshot, OCR text, and evidence in the review console to inspect why a document was misclassified or rejected.
2. **Use medium severity for unknown documents**:
   - *Rejected*: A document that cannot be identified as an invoice cannot be cleared for payment under any circumstance. High severity ensures an urgent review requirement.

## Consequences

- Purchase orders and unknown/unclassified documents can never receive an unearned `clear` verdict.
- Genuine invoices (`document_type == "invoice"`) pass the check with zero findings and zero performance overhead.
- Strictly adheres to the pure, deterministic verification architecture and preserves input immutability.
