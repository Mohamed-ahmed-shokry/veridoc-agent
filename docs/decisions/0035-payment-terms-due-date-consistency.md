# 0035: Payment terms and due date consistency verification

## Status

Accepted

## Context

In commercial accounts payable (AP) operations, the contractual credit window between an invoice's
issue date (`invoice_date`) and payable due date (`due_date`) is governed by agreed payment terms
(`payment_terms`), such as "Net 30", "Net 15", "Net 60", "Net 90", or "Due on receipt".

Previously in Veridoc:
1. `check_invoice_dates` in `veridoc.verification.arithmetic` only checked that `invoice_date <= due_date`.
   An invoice stating "Net 30" with a due date only 3 days after the invoice date cleared date verification
   without review.
2. `check_payment_terms` in `veridoc.verification.field_history` only compared `invoice.payment_terms`
   against *historical* payment terms from prior vendor invoices. It did not cross-check whether
   the invoice's own extracted `due_date` agreed with its stated `payment_terms` and `invoice_date`.

As a result, two major categories of financial and extraction anomalies evaded automated detection:
1. **Predatory term acceleration / Early due dates**:
   The invoice header specifies standard credit terms (e.g. "Net 30"), but the printed `due_date` is
   accelerated (e.g. 5 or 10 days after `invoice_date`). This unfairly reduces buyer liquidity, attempts
   to trigger illegitimate late-payment penalties, and pressures AP teams into premature cash outflows.
2. **Due date calculation errors & extraction mismatches**:
   Vendor invoicing software errors (e.g. month-number transposition or calendar math bugs) or OCR
   extraction errors (e.g. extracting a discount cutoff date, statement date, or shipping date instead
   of the final net due date) cause `due_date` to diverge from `invoice_date + payment_terms_days`.

## Decision

Phase 28 introduces:

1. **`parse_payment_terms_days(terms: str | None) -> int | None`**:
   - Pure deterministic parser supporting standard commercial credit terms:
     - `Net <N>`, `NET <N>`, `Net <N> days` (e.g. `Net 10`, `Net 15`, `Net 30`, `Net 45`, `Net 60`, `Net 90`, `Net 120`).
     - Cash discount notation: `<D>/<T> Net <N>` (e.g. `2/10 Net 30`, `1/10 Net 30`) where net credit period is $N$ days.
     - Immediate terms: `Due on receipt`, `Due upon receipt`, `Immediate`, `Payment on receipt`, `Cash on delivery`, `COD` (0 days).
   - Case-insensitive, whitespace-trimmed, punctuation-tolerant parsing.
   - Non-standard, free-form, or unrecognized terms safely return `None` (no speculative guessing).

2. **Weekend Business-Day Adjustment**:
   - If `expected_due_date = invoice_date + timedelta(days=terms_days)` falls on a Saturday and `observed_due_date` is Monday (+2 days), or falls on a Sunday and `observed_due_date` is Monday (+1 day), the due date is recognized as a standard business-day roll and accepted without a finding.

3. **`payment_terms_due_date_mismatch` finding type**:
   - Added to `FindingType` in `veridoc.verification.models`.
   - Comparison source: `"invoice_fields"`.
   - Deterministic rule: `"invoice.due_date == invoice.invoice_date + payment_terms_days"`.
   - Severity:
     - `high` when `observed_due_date < expected_due_date` (accelerated due date / shortened credit window).
     - `medium` when `observed_due_date > expected_due_date` exceeding any weekend roll (extended due date / calculation error).
   - Structured details include:
     `"payment_terms"`, `"terms_days"`, `"expected_due_date"`, `"observed_due_date"`, `"discrepancy_days"`, `"is_accelerated"`.

4. **Pure Function and Service Integration**:
   - Pure function `check_payment_terms_due_date(invoice)` implemented in `veridoc.verification.payment_terms`.
   - Wired into `VerificationService.verify()`, routing violating invoices to `review_required`.

## Consequences

- Invoices with accelerated due dates are immediately flagged with `high` severity to protect buyer working capital.
- Invoices with calendar math or extraction mismatches are flagged with `medium` severity for reviewer reconciliation.
- Standard commercial weekend payment date rolls (Saturday/Sunday to Monday) are natively supported without false positives.
- Non-standard or unparseable payment terms safely bypass the check without false alarms.
