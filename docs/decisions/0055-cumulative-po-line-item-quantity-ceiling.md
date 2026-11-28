# 0055: Cumulative purchase-order line-item quantity ceiling verification

## Status

Accepted

## Context

Phase 16 (ADR 0026) established one-sided purchase-order authorization ceilings: `check_purchase_order` enforces `invoice.total <= purchase_order.total` and `invoice.line_item.quantity <= purchase_order.line_item.quantity` for a single invoice, and `check_purchase_order_ceiling` enforces cumulative `sum(prior.total) + invoice.total <= purchase_order.total` across prior historical invoices referencing the same PO. However, `check_purchase_order_ceiling` evaluates only the header total. When a purchase order authorizes multiple line items (for example, 10 units of Widget A at \$50 and 10 units of Widget B at \$100; PO total \$1500), a supplier can bill 8 units of Widget A on Invoice 1 (\$400) and 6 units of Widget A on Invoice 2 (\$300). Each individual invoice stays under the single-invoice quantity limit (`6 <= 10`) and the cumulative total stays under the PO total (`\$700 <= \$1500`), yet Widget A is cumulatively over-billed (`14 > 10`).

## Decision

1. **Reuse `purchase_order_mismatch` Finding Type**: Emit `finding_type="purchase_order_mismatch"` with `severity="high"` and `comparison_source="purchase_order"`, mirroring the header cumulative ceiling in `check_purchase_order_ceiling` (ADR 0026) and distinguishing line-item quantity ceiling violations via `details={"field": "purchase_order_billed_line_item_quantity", "line_item_key": key, "prior_invoice_count": prior_count}`.
2. **Authorized Quantity Aggregation**: Aggregate authorized quantities per canonical `line_item_key` across `purchase_order.line_items` using exact `Decimal` arithmetic. If any PO line sharing a key omits `quantity` (`None`), conservatively exclude that key so partial PO metadata cannot trigger false positives.
3. **Prior-History Filtering & Deduplication**: Accumulate prior quantities and distinct `prior_invoice_count` per `line_item_key` across `history` entries referencing the same `purchase_order_number` with compatible currency (both absent or equal). Skip keys with `prior_invoice_count == 0`, because single-invoice line-item over-billing is already owned exclusively by `check_purchase_order`.
4. **Header-Total Independence**: Evaluate line-item quantity ceilings inside `check_purchase_order_ceiling` whenever `_comparable_amounts(invoice, purchase_order)` holds, even when `purchase_order.total` or `invoice.total` is `None`.
5. **Service Integration**: Because `VerificationService.verify()` already invokes `check_purchase_order_ceiling(invoice, self._repository, history)`, cumulative line-item quantity over-billing routes deterministically to `review_required` with zero additional repository queries.

## Alternatives Considered

- **Introduce a new `FindingType` literal (e.g., `po_line_item_quantity_ceiling_exceeded`)**: Rejected because ADR 0026 explicitly keeps all purchase-order authorization violations under `purchase_order_mismatch` distinguished by `details["field"]` (`total`, `line_item_quantity`, `purchase_order_billed_total`).
- **Evaluate line-item ceilings only when `purchase_order.total` is present**: Rejected because line-item-only POs (without a header total) still define authoritative per-item quantity ceilings that split invoices can exceed.

## Consequences

- **Positive**: Split over-billing of individual PO line items is deterministically caught even when the cumulative header total remains within the PO total.
- **Neutral**: Single-invoice over-billing continues to emit only `line_item_quantity` from `check_purchase_order`, avoiding duplicate findings; POs with omitted line quantities pass safely without false positives.
- **Negative**: None; pure `Decimal` aggregation over already-loaded vendor history with zero schema or repository changes.
