# 0040: Line item completeness and derived subtotal verification

## Status

Accepted

## Context

Phase 33 requires the four header fields every identity, date, and money rule
depends on. Invoice line items remained a separate blind spot:

- `line_item_key` returns `None` when both `product_identifier` and
  `description` are absent or blank. Duplicate detection, historical occurrence,
  historical price/quantity statistics, and purchase-order line matching all
  skip such a line silently, so an unidentifiable line cannot be reconciled at
  all.
- A line item may carry no monetary data, or only one of quantity and unit
  price. Its amount is then neither verifiable by `check_line_item_amounts` nor
  usable by `check_line_items_subtotal`.
- `check_line_items_subtotal` returned early when any `total_price` was absent,
  even when `quantity` and `unit_price` made the line amount derivable. A single
  missing line total therefore disabled subtotal verification for the whole
  invoice, leaving a vacuous-clear path behind the Phase 33 header checks.

These are completeness defects rather than sign or arithmetic defects. They are
deterministic, do not require jurisdiction-specific thresholds, and are
orthogonal to the existing rules that judge present values.

## Decision

Phase 34 adds line-item completeness verification and closes the derived
subtotal bypass:

1. **`incomplete_line_item` finding type**:
   - Added to `FindingType` in `veridoc.verification.models`.
   - Comparison source: `"invoice_line_items"`.
   - One finding per missing requirement per line item, emitted in line-item
     order with identity checked before amount.
   - Severity: `"medium"` for both requirements.
   - Structured details: `{"line_item_index": <index>, "field": "identity" |
     "amount"}`.

2. **Identity requirement**:
   - A line item must have a non-blank `product_identifier` or `description`.
   - Deterministic rule:
     `"line_item.product_identifier or line_item.description is present"`.
   - Reuses `line_item_key` so blank strings count as absent, matching every
     existing reconciliation rule.

3. **Amount requirement**:
   - A line item must have `total_price`, or both `quantity` and `unit_price`.
   - Deterministic rule:
     `"line_item.total_price is not None or (line_item.quantity is not None and line_item.unit_price is not None)"`.
   - The rule deliberately does not judge sign or value; Phases 25 and 27 keep
     that responsibility.
   - `total_price=0` is present and therefore complete.

4. **Pure function**:
   - `check_line_item_completeness(invoice)` in
     `veridoc.verification.line_item_completeness` returns `[]` for no line
     items or for line items satisfying both requirements, and never mutates the
     input.

5. **Derived line totals in subtotal verification**:
   - `check_line_items_subtotal` adds `total_price` when present and otherwise
     derives `quantity * unit_price` when both are present.
   - It returns `[]` only when a line amount still cannot be derived; that line
     is reported by the completeness rule instead.
   - Rounding tolerance and all existing mismatch/rounding finding contracts are
     unchanged.

6. **Service integration**:
   - `VerificationService.verify()` calls `check_line_item_completeness` after
     header completeness and before arithmetic, so line-level gaps are always
     reported first.

## Alternatives Considered

1. **Require only identity, ignoring amount derivability**:
   - *Rejected*: an unidentifiable line and a line with no usable amount are both
     unreconcilable, and the subtotal bypass would remain.
2. **Require `total_price` unconditionally**:
   - *Rejected*: many legitimate invoices print quantity and unit price but omit
     the printed line total, and the amount is still deterministic.
3. **Reject invoices with unidentified line items at extraction time**:
   - *Rejected*: verification owns trust decisions and review snapshots must
     retain the evidence.
4. **Leave `check_line_items_subtotal` early-return behavior unchanged**:
   - *Rejected*: it is the concrete vacuous-clear path this phase exists to
     close; deriving a deterministic amount is strictly more informative.
5. **Use `high` severity**:
   - *Rejected*: these are completeness gaps requiring review, not confirmed
     fraud indicators. `medium` matches extraction-uncertainty and
     payment-terms-change severity while still forcing `review_required`.

## Consequences

- Line items that cannot be identified or priced can no longer be skipped
  silently by reconciliation or subtotal checks.
- Invoices with printed quantity and unit price but no printed line total now
  receive full subtotal verification instead of no verification.
- Reviewers see field-addressable line-item findings suitable for console
  filtering and auditor evidence.
- Extraction schemas, persistence, prompts, and evaluation manifests are
  unchanged. Invoices with no line items remain valid.
