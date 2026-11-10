# 0044: Excessive tax amount verification

## Status

Accepted

## Context

In accounts payable and commercial document intelligence, invoice tax amounts (sales tax, VAT,
GST) represent statutory levies calculated as a bounded percentage of the taxable supply (`subtotal`).
Across global tax jurisdictions, standard statutory VAT and sales tax rates range from 0% (zero-rated,
exempt, or reverse-charge supplies) up to a maximum standard rate of approximately 27% (the highest
standard VAT rate among OECD member states, in Hungary). Even when combined with state, municipal, or
special excise surcharges, lawful commercial taxes on standard B2B transactions never exceed 100% of the
taxable supply.

In Phase 26 (ADR 0033), `check_header_amounts` established initial header monetary bounds:
1. `subtotal > 0` (negative = high severity, zero = medium severity);
2. `tax >= 0` (negative = high severity); and
3. `0 <= discount <= subtotal` (negative = high severity, discount > subtotal = high severity).

While `discount > subtotal` was explicitly prohibited because a commercial discount cannot exceed the
taxable base, `tax` was only checked for non-negativity (`tax >= 0`). Consequently, an invoice where
vision/OCR models misread decimal placement (e.g. transcribing a \$15.00 tax on a \$100.00 subtotal as
\$150.00 tax), transpose the tax field with the invoice total, or hallucinate an extra digit passes
all existing verification rules and receives an unearned `clear` verdict if the arithmetic total happens
to match or if subtotal and total are evaluated without an upper tax bound.

Allowing invoices with `tax > subtotal` (or `tax > total` when subtotal is omitted) to clear automated
reconciliation creates severe financial and compliance vulnerabilities:
1. **Financial Overpayment**: Accounts payable straight-through processing could disburse payments for
   hallucinated or transposed tax figures, resulting in overpayment and difficult recovery cycles.
2. **Tax Compliance Discrepancies**: In input VAT / sales tax recovery reporting, claiming tax credits
   exceeding the base invoice amount invites mandatory tax authority audits, penalties, and disallowances.
3. **OCR Misread Blindspot**: Transpositions between tax and total or runaway decimal misreads are
   classic OCR failure modes that deterministic rules must intercept.

Establishing a deterministic upper bound (`tax <= subtotal` when `subtotal > 0`, and `tax <= total` when
`subtotal` is absent) ensures that any invoice carrying an impossible tax liability is flagged with
`high` severity, routing the invoice to mandatory human review (`review_required`).

## Decision

Phase 38 introduces:

1. **`excessive_tax` finding type**:
   - Added to `FindingType` in `veridoc.verification.models`.
   - Comparison source: `"invoice_fields"`.
   - Severity: `"high"`.
   - Deterministic rule: `"invoice.tax <= invoice.subtotal"` (or `"invoice.tax <= invoice.total"` when subtotal is omitted).
   - Structured details include:
     `"field": "tax"`, `"tax"`, `"subtotal"`, `"effective_tax_rate"`, `"max_tax_rate"` (or `"total"`).

2. **Upper bound threshold**:
   - Default upper bound ratio is `DEFAULT_MAX_TAX_TO_SUBTOTAL_RATIO = Decimal("1.00")` (100% of subtotal).
   - Parametrized in `check_excessive_tax(invoice, max_tax_rate=Decimal("1.00"))` to allow tighter commercial configurations if needed.

3. **Exclusion paths (pure function safety)**:
   - Returns `[]` when `tax` is `None` or `tax <= Decimal(0)` (negative tax is owned by Phase 26 `negative_tax`).
   - Returns `[]` when `subtotal <= Decimal(0)` or `total <= Decimal(0)` (non-positive subtotals/totals are owned by Phase 24/26).
   - Returns `[]` when both `subtotal` and `total` are `None`.
   - Returns `[]` when `tax <= subtotal * max_tax_rate` (or `tax <= total`).

4. **Triggering paths**:
   - When `subtotal > 0` and `tax > subtotal * max_tax_rate`, emits one `high`-severity `excessive_tax` finding.
   - When `subtotal is None`, `total > 0`, and `tax > total`, emits one `high`-severity `excessive_tax` finding.

5. **Input immutability**:
   - Pure function that never mutates the input extraction.

6. **Service integration**:
   - Integrated into `VerificationService.verify()`, routing any finding to `review_required`.

## Consequences

- Invoices with decimal misreads, transposed tax fields, or hallucinated tax amounts exceeding the taxable base are deterministically caught.
- Legitimate commercial invoices with standard global tax rates (0% through 27%) or special rates up to 100% pass without false positives.
