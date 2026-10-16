# 0036: Excessive credit window and due date bound verification

## Status

Accepted

## Context

In commercial business-to-business (B2B) trade and accounts payable (AP) operations, the credit
window between invoice issue date (`invoice_date`) and payable due date (`due_date`) is governed
by standard trade credit conventions. Typical credit terms range from immediate payment (Net 0) up
to standard quarterly windows (Net 30, Net 60, Net 90, and rarely Net 120 or Net 180 for complex
capital goods or seasonal financing).

While Phase 28 (ADR 0035) introduced `payment_terms_due_date_mismatch` to detect inconsistencies
when explicit `payment_terms` (such as "Net 30") are extracted, many invoices lack an explicit
payment terms string or contain non-standard free-form text. In such cases, `payment_terms_due_date_mismatch`
cannot evaluate the credit window.

However, an invoice whose `due_date` extends excessively far beyond `invoice_date` represents a severe
financial and operational anomaly:
1. **Vision/OCR Year or Month Hallucination**:
   OCR errors frequently misread year numbers (e.g. transposing 2026 to 2036 or 2062) or confuse
   due dates with multi-year contract expiration dates, equipment warranty termination dates, or lease terms.
2. **Zombie Liability and Aging Distortions**:
   Recording an invoice due 1, 2, or 10 years in the future distorts cash forecasting, accounts payable
   aging reports, liquidity metrics, and working capital schedules.
3. **Sham Transactions and Audit Inconsistencies**:
   Excessive deferral of payment obligations can be used in fictitious invoicing schemes to manipulate
   balance sheet liabilities without triggering near-term cash disbursement alarms.

In commercial AP best practice, any invoice with an extracted credit window exceeding 365 days
(`MAXIMUM_CREDIT_WINDOW_DAYS = 365`) is commercially abnormal and must be flagged for human review.

## Decision

Phase 30 introduces:

1. **`MAXIMUM_CREDIT_WINDOW_DAYS = 365`**:
   - Pure constant defining the upper bound of standard commercial credit windows (1 year / 365 calendar days).
   - Invoices with `(due_date - invoice_date).days > MAXIMUM_CREDIT_WINDOW_DAYS` trigger verification review.

2. **`excessive_due_date_window` finding type**:
   - Added to `FindingType` in `veridoc.verification.models`.
   - Comparison source: `"invoice_fields"`.
   - Deterministic rule: `"due_date - invoice_date <= 365 days"`.
   - Severity: `"medium"`.
   - Structured details include:
     `"credit_window_days"`, `"max_allowed_days"` (365), `"invoice_date"`, `"due_date"`.

3. **Exclusion Paths (Pure Function Safety)**:
   - Returns `[]` when `invoice_date` is `None` or `due_date` is `None`.
   - Returns `[]` when `due_date < invoice_date` (this condition is owned and reported by `invoice_date_after_due_date` in arithmetic checks).
   - Returns `[]` when `(due_date - invoice_date).days <= 365`.

4. **Pure Function and Service Integration**:
   - Implemented in `veridoc.verification.due_date_bounds.check_excessive_due_date_window(invoice)`.
   - Integrated into `VerificationService.verify()`, routing violating invoices to `review_required`.

## Consequences

- Invoices with hallucinated due years, multi-year warranty misextractions, or abnormal multi-year payment terms are reliably flagged.
- Legitimate commercial credit windows up to a full year (Net 30, Net 60, Net 90, Net 120, Net 180, Net 360, Net 365) pass without false positives.
- Seamlessly complements Phase 28 (which validates explicit contractual terms) by providing an absolute upper bound when payment terms are absent or unparseable.
- Input immutability is strictly preserved.
