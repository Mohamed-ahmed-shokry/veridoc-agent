# 0032: Detect non-positive line item amounts and quantities

## Status

Accepted

## Context

The verification layer validates internal arithmetic (subtotals, line-item
multiplication, discounts, tax, total equality), temporal validity (future issue
dates, historical staleness, due date ordering), duplicate invoice numbers,
duplicate line items within an invoice, purchase-order authorization ceilings,
vendor master registry compliance, and overall invoice total positivity
([ADR 0031](0031-non-positive-invoice-total-detection.md)). However, it lacks any
validation of the positivity of individual line items within an invoice.

In commercial accounts payable and document intelligence, each invoice line item
(`InvoiceLineItem`) represents an individual good or service delivered and billed
for payment. Under standard accounting principles (GAAP, IFRS) and internal
billing controls, commercial line items must specify strictly positive values
for delivered quantity (`quantity > 0`), unit price (`unit_price > 0`), and line
total amount (`total_price > 0`).

Two distinct risk patterns produce invoices with non-positive line items:

1. **Negative line items (`total_price < 0`, `unit_price < 0`, `quantity < 0`)** —
   A line item with a negative total, unit price, or quantity indicates an
   unauthorized credit line, return allowance, trade-in deduction, or rebate
   offset embedded directly into an invoice. In accounts payable workflows,
   credits cannot be netted against standard billing without explicit credit memo
   authorization and debit-reversal processing. Netting negative line items
   inside an invoice distorts sales tax / VAT calculations across mixed-rate
   supplies, bypasses purchase-order line authorization ceilings, and evades AP
   approval thresholds. Furthermore, negative line items frequently arise from
   vision/OCR extraction defects where hyphens, dashes, bullet points, or glyphs
   are erroneously transcribed as negative signs (e.g. `-100.00` instead of
   `100.00`), silently corrupting line-item data.
2. **Zero line items (`total_price == 0`, `unit_price == 0`, `quantity == 0`)** —
   A line item specifying a zero quantity (`quantity == 0`) indicates an
   operational anomaly: billing for goods or services where zero units were
   delivered. A line item with a zero unit price or zero line total
   (`unit_price == 0` or `total_price == 0`) represents promotional samples,
   zero-dollar warranty replacements, unpriced services, or an OCR extraction
   dropout where the price was blanked or misparsed as zero. Allowing zero-value
   line items to pass without review risks accepting unauthorized promotional
   charges, missing unextracted prices, or fulfilling phantom purchase-order lines.

Currently, if an extracted invoice contains line items with negative or zero
values whose internal multiplication balances (for example, `quantity = -2,
unit_price = 50.00, total_price = -100.00`, or `quantity = 0, unit_price = 10.00,
total_price = 0.00`), `check_line_item_amounts` in `arithmetic.py` passes because
the mathematical equation `quantity * unit_price == total_price` holds.
`check_line_items_subtotal` passes because the negative or zero amount is simply
summed into the subtotal. If the invoice total remains positive (netted against
positive line items), `check_non_positive_invoice_total` does not fire. The invoice
thus evades every verification check and receives an unearned `clear` processing
verdict. Flagging non-positive line items for human review closes this critical
commercial verification gap.

## Decision

Phase 25 introduces a `non_positive_line_item` finding type and a pure
deterministic function `check_non_positive_line_items` in
`veridoc.verification.line_item_amounts`:

- The rule inspects each line item in `invoice.line_items`.
- Only observed, non-null values for `quantity`, `unit_price`, and `total_price`
  are evaluated. Null/absent fields (`None`) are ignored, preserving the principle
  that unextracted optional fields are handled via extraction uncertainty flags
  rather than arithmetic positivity violations.
- When any observed field on a line item is non-positive (`<= Decimal(0)`),
  exactly one `non_positive_line_item` finding is generated for that line item.
- Severity is differentiated based on financial and fraud risk:
  - **`high` severity** if **any observed non-positive field is strictly negative**
    (`total_price < Decimal(0)`, `unit_price < Decimal(0)`, or
    `quantity < Decimal(0)`): Negative line items indicate unauthorized credit
    lines, returns, trade-ins, or minus-sign OCR errors posing direct ledger and
    tax compliance risks.
  - **`medium` severity** if **all observed non-positive fields are zero**
    (`total_price == Decimal(0)`, `unit_price == Decimal(0)`, or
    `quantity == Decimal(0)`): Zero-value line items represent promotional
    samples, placeholder rows, or price extraction dropouts requiring review.
- `comparison_source` is `"invoice_line_items"`.
- `deterministic_rule` is `"line_item.quantity > 0 and line_item.unit_price > 0 and line_item.total_price > 0"`.
- `observed_value` summarizes the non-positive field values (e.g. `"total_price=-10.00"`
  or `"quantity=-1, total_price=-10.00"`).
- `expected_value` is `"> 0.00"`.
- `details` includes:
  - `"line_item_index"`: 0-based integer index of the line item;
  - `"product_identifier"`: extracted product identifier if present;
  - `"description"`: extracted line item description if present;
  - `"field"`: comma-separated list of non-positive fields (e.g. `"total_price"` or `"quantity, total_price"`);
  - `"is_negative"`: boolean indicating whether any field was strictly negative;
  - `"is_zero"`: boolean indicating whether all non-positive fields were zero;
  - individual non-positive field values as strings (e.g. `"total_price": "-10.00"`).

`VerificationService.verify()` calls `check_non_positive_line_items` alongside
`check_arithmetic`, `check_non_positive_invoice_total`, `check_duplicate_line_items`,
`check_invoice_staleness`, and `check_future_invoice_date`. No database migration,
repository changes, or external service dependencies are required.

## Alternatives considered

- *Merge the check into `_check_line_item_amounts` in `arithmetic.py`.*
  Rejected: `arithmetic.py` validates mathematical equality among extracted
  relational fields (`quantity * unit_price == total_price`). Positivity of line
  items is an accounts payable commercial integrity rule, not an equation
  equality failure (since negative numbers satisfy multiplication equality).
  Placing it in a dedicated module (`veridoc.verification.line_item_amounts`)
  preserves modularity and matches the architecture of `duplicate_line_items.py`
  and `invoice_totals.py`.
- *Emit separate findings for each non-positive field on a line item.*
  Rejected: If a line item has a negative quantity and a negative total, emitting
  two separate findings creates noisy duplication for a single line item.
  Emitting a single finding with composite field details and appropriate severity
  provides clearer operational guidance to human reviewers.
- *Treat both zero and negative line items with uniform severity.*
  Rejected: Negative line items present immediate risks of credit netting fraud,
  VAT distortion, and spend limit bypass, demanding `high` severity. Zero-value
  line items frequently represent legitimate zero-dollar promotional samples or
  unpriced lines that require confirmation (`medium` severity) rather than
  critical rejection.

## Consequences

- The `FindingType` literal union in `veridoc.verification.models` expands by
  `"non_positive_line_item"`. Processing schemas remain backwards-compatible,
  and no database migrations or schema validations are affected.
- Invoices containing negative line items or zero-quantity/zero-amount line items
  are deterministically flagged and routed to `review_required` rather than
  receiving an unearned `clear` verdict.
- Explanation generation, evaluation metrics, and review case snapshots
  seamlessly handle the new finding type via existing polymorphic finding
  structures.
