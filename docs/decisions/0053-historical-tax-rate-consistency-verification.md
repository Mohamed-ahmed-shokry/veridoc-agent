# 0053: Historical effective tax rate consistency verification

## Status

Accepted

## Context

Veridoc validates tax non-negativity (`tax >= 0`, ADR 0033) and statutory upper bounds (`tax <= subtotal`, ADR 0044), while historical total checks (`check_historical_total`) compare invoice grand totals against 3-sigma historical ranges. However, if a vendor consistently invoices with a fixed effective tax rate (e.g., 20% VAT or 0% exempt) and an incoming invoice arrives with a shifted tax rate (e.g., 0% or 10% or 40%) while still balancing `subtotal + tax == total` and remaining within 3-sigma of historical totals, no deterministic rule currently flags the tax-rate anomaly.

## Decision

1. **New Finding Type**: Add `historical_tax_rate_mismatch` to `FindingType` in `veridoc.verification.models`.
2. **Exact Decimal Ratio & Tolerance**: Define `TAX_RATE_TOLERANCE = Decimal("0.005")` (0.5 percentage points) and `TAX_RATE_PRECISION = Decimal("0.0001")` in `veridoc.verification.field_history`, computing effective tax rate as `(tax / subtotal).quantize(TAX_RATE_PRECISION)` for `subtotal > 0` and `tax >= 0`.
3. **Exclusion Paths**: Emit `[]` when `invoice.currency`, `invoice.subtotal`, or `invoice.tax` is absent, when `subtotal <= 0` or `tax < 0`, when fewer than `MINIMUM_HISTORY_SAMPLE_SIZE` (3) same-currency historical invoices have valid tax rates, when historical rates vary by more than `tolerance` (`max - min > tolerance`), or when `abs(observed_rate - expected_rate) <= tolerance`.
4. **Triggering Path**: Emit one `medium`-severity `historical_tax_rate_mismatch` finding with `comparison_source="vendor_history"`, `historical_sample_size`, formatted percentage `observed_value` / `expected_value`, and structured `details` (`field="tax"`, `currency`, `observed_tax_rate`, `expected_tax_rate`, `tolerance`).
5. **Service Integration**: Invoke `check_historical_tax_rate(invoice, history)` in `VerificationService.verify()`, routing tax-rate anomalies to `review_required`.

## Consequences

- **Positive**: Unexpected VAT/tax-rate shifts and omitted-tax anomalies for consistent-rate suppliers are deterministically flagged for human review.
- **Neutral**: Multi-rate vendors (e.g., mixed standard and reduced-rate supplies) and low-history vendors pass without false positives.
- **Negative**: None; pure `Decimal` function with zero schema changes.
