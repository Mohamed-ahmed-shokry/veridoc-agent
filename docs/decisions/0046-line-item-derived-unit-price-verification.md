# 0046: Line-item derived unit price arithmetic verification

## Status

Accepted

## Context

In invoice processing and accounts payable reconciliation, line items often present
varied visual structures. In many commercial invoices:
1. Vendors provide `quantity` and `total_price` for services or standard deliverables
   while omitting an explicit `unit_price` column.
2. OCR and vision extraction models sometimes miss the `unit_price` column or field,
   leaving `line_item.unit_price is None` while `quantity` and `total_price` are captured
   accurately.
3. In Phase 34 (ADR 0040), Veridoc established that line items without `total_price` can
   derive their line total from `quantity * unit_price` when computing `check_line_items_subtotal`.
4. However, the inverse path has been omitted: when `total_price` and `quantity` are present,
   `check_line_item_statistics` (historical price outlier detection) checks `line_item.unit_price`.
   When `unit_price` is `None`, historical line item price outlier analysis silently skips the item,
   even though the effective unit price is deterministically knowable as `total_price / quantity`.
5. Furthermore, when `quantity == 0` or negative, direct division would cause runtime exceptions
   or non-physical unit prices if not guarded safely.

To ensure consistency across deterministic verification rules and eliminate blind spots in
historical price outlier detection, Veridoc needs a safe, standard mechanism to derive unit price
when `unit_price` is absent, and apply it transparently to historical statistics evaluation.

## Decision

1. **Pure Helper Function**: Introduce `derive_unit_price(quantity: Decimal | None, total_price: Decimal | None) -> Decimal | None` in `veridoc.verification.arithmetic`.
   - Returns `None` if either argument is `None` or if `quantity <= 0`.
   - Computes `(total_price / quantity).quantize(Decimal("0.0001"))` to maintain 4 decimal places of precision standard in commercial unit pricing.
   - Never raises `DivisionByZero` or `InvalidOperation`.
2. **Transparent Historical Outlier Analysis**:
   - In `veridoc.verification.line_items.check_line_item_statistics`, if `line_item.unit_price` is `None`,
     attempt to evaluate `derive_unit_price(line_item.quantity, line_item.total_price)`.
   - If a valid derived unit price is obtained and an outlier is detected against vendor history, emit
     `historical_line_item_price_outlier` with `details["derived_unit_price"] = True` and
     `details["observed_unit_price"] = str(derived_price)`.
3. **No Schema Mutation**:
   - `InvoiceLineItem` objects remain strictly immutable. The extracted data is never mutated.
4. **Preserve Phase 25 and 34 Behaviors**:
   - Zero and negative quantities continue to trigger `non_positive_line_item` findings via Phase 25.
   - Missing identities continue to trigger `incomplete_line_item` via Phase 34.

## Consequences

- Invoices omitting `unit_price` on line items can now be evaluated for abnormal unit prices against vendor historical baselines.
- Zero or negative quantities never cause division by zero errors during verification.
- Immutability of extraction schemas and historical records is preserved.
