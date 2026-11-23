# 0052: Historical currency consistency verification

## Status

Accepted

## Context

In Veridoc's vendor-history verification (`veridoc.verification.history`, `veridoc.verification.line_items`, `veridoc.verification.field_history`), statistical and payment-term comparisons filter historical invoices by `historical_invoice.currency == invoice.currency`. While this prevents comparing monetary amounts across incompatible currencies, it leaves a blind spot: when a single-currency vendor's invoice arrives with a different currency (for example due to an OCR symbol misread such as `€` vs `$` or an unexpected billing-currency switch), same-currency filters yield zero matching history and emit only `insufficient_history` (`info`).

## Decision

1. **New Finding Type**: Add `historical_currency_mismatch` to `FindingType` in `veridoc.verification.models`.
2. **Pure Verification Rule**: Implement `check_historical_currency(invoice, history)` in `veridoc.verification.field_history`.
3. **Exclusion Paths**: Emit `[]` when `invoice.currency` is `None`, when fewer than `MINIMUM_HISTORY_SAMPLE_SIZE` (3) historical invoices carry a non-blank currency, when historical invoices span multiple distinct currencies, or when `invoice.currency` matches the consistent historical currency (case- and whitespace-normalized).
4. **Triggering Path**: Emit one `medium`-severity `historical_currency_mismatch` finding with `comparison_source="vendor_history"`, `historical_sample_size`, `observed_value`, `expected_value`, and structured `details` (`field="currency"`, `observed_currency`, `expected_currency`).
5. **Service Integration**: Invoke `check_historical_currency(invoice, history)` in `VerificationService.verify()`, routing unexpected currency changes to `review_required`.

## Consequences

- **Positive**: Unexpected currency changes and OCR currency misreads for established single-currency vendors are deterministically flagged for human review.
- **Neutral**: Multi-currency vendors and low-history vendors continue to pass without false positives.
- **Negative**: None; pure function with zero side effects or schema changes.
