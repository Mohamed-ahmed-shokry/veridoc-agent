# 0034: Invoice arithmetic tolerances and fractional rounding bounds

## Status

Accepted

## Context

Veridoc's deterministic verification layer evaluates arithmetic consistency across
extracted invoice facts in `veridoc.verification.arithmetic`:
1. `_check_invoice_total`: compares `subtotal + tax - discount == total`.
2. `_check_line_item_amounts`: compares `quantity * unit_price == total_price` for each line item.
3. `_check_line_items_subtotal`: compares `sum(line_item.total_price) == subtotal`.

Two distinct limitations in the previous implementation caused operational failures:

1. **Zero tolerance for standard fractional rounding variances**:
   Under international commercial invoicing and VAT/sales tax rules (such as Peppol BIS Billing 3.0 /
   EN 16931 rules BR-CO-10 and BR-CO-15, and HMRC/IRS rounding guidelines), rounding differences
   between item-level calculations and document-level tax or subtotal calculations naturally arise.
   For example, when multiple line items have fractional unit prices (e.g. $33.3333 rounded to $33.33
   on a printed invoice for 3 units, totaling $100.00 rather than $99.99) or when percentage sales taxes
   (e.g. 8.25% or 7.7%) are computed per line item and summed versus computed on the overall subtotal,
   independent half-up rounding produces a 1-cent or 2-cent ($0.01 - $0.02) variance.

   Previously, Veridoc enforced exact, zero-tolerance decimal equality (`total == expected_total`,
   `total_price == quantity * unit_price`, `subtotal == expected_subtotal`). Any discrepancy—even
   $0.01—triggered a `high`-severity finding (`invoice_total_mismatch`, `line_item_amount_mismatch`,
   `line_items_subtotal_mismatch`), driving the entire processing verdict to `review_required` at the
   highest severity level. This equated benign penny-rounding variances with severe systemic fraud or
   catastrophic extraction errors.

2. **Skipping header total check when discount or tax is omitted**:
   `_check_invoice_total` previously checked `if subtotal is None or tax is None or discount is None or total is None: return []`.
   On commercial invoices, discounts are omitted (`None`) on the vast majority (over 90%) of invoices
   rather than explicitly printed as `0.00`. Requiring all four fields to be non-null meant that
   standard invoices without discounts completely bypassed header total verification. An invoice with
   `subtotal = 100.00`, `tax = 20.00`, `discount = None`, and `total = 999.00` received zero findings
   from `_check_invoice_total`.

## Decision

Phase 27 introduces:

1. **`DEFAULT_ROUNDING_TOLERANCE: Final[Decimal] = Decimal("0.02")`**:
   - Establishes a standard commercial rounding tolerance of 2 minor currency units (e.g. 0.02 USD / EUR).
   - Can be optionally overridden via `rounding_tolerance: Decimal` parameter on arithmetic verification functions.

2. **`rounding_discrepancy` finding type**:
   - Added to `FindingType` in `veridoc.verification.models` with `severity="low"`.
   - Emitted whenever the absolute difference between observed and expected amounts is strictly positive
     and within the rounding tolerance (`0 < discrepancy <= rounding_tolerance`).
   - Structured details record `"discrepancy"`, `"tolerance"`, `"component"` (`"invoice_total"`,
     `"line_item_amount"`, or `"line_items_subtotal"`), and contextual attributes (e.g. `currency`,
     `line_item_index`, `line_item_count`).

3. **Material mismatch retention**:
   - Whenever discrepancy strictly exceeds `rounding_tolerance` (`discrepancy > 0.02`), the rule emits
     the existing `high`-severity finding:
     - `invoice_total_mismatch`
     - `line_item_amount_mismatch`
     - `line_items_subtotal_mismatch`
   - Details preserve `"discrepancy"` and `"tolerance"`.

4. **Normalized omitted discount and tax handling in `_check_invoice_total`**:
   - When `invoice.subtotal` and `invoice.total` are present:
     - If both `tax` and `discount` are present: `expected = subtotal + tax - discount`.
     - If `tax` is present and `discount is None`: `expected = subtotal + tax` (omitted discount treated as `0.00`).
     - If `discount` is present and `tax is None`: `expected = subtotal - discount` (omitted tax treated as `0.00`).
     - If both `tax` and `discount` are `None`:
       - If `subtotal == total`: exact match, returns `[]`.
       - If `subtotal != total`: returns `[]` (indeterminate whether tax or discount was omitted from extraction).

5. **Exposed public interface**:
   - `check_invoice_total`, `check_line_item_amounts`, `check_line_items_subtotal`, and `check_invoice_dates`
     are exported as public functions in `veridoc.verification.arithmetic`, with `check_arithmetic` composing them.

## Consequences

- Invoices with minor penny rounding differences (<= 0.02) receive `rounding_discrepancy` with `low` severity,
  allowing straight-through processing or low-priority routing without false alarms.
- Material calculation errors (> 0.02) continue to trigger `high`-severity mismatch findings.
- Standard invoices without discounts now have their header totals verified.
- Existing tests and ground truth fixtures continue to pass.
