# 0033: Enforce invoice header monetary bounds for subtotal, tax, and discount

## Status

Accepted

## Context

The verification layer validates internal arithmetic equality
(`subtotal + tax - discount == total` and `sum(line_item.total_price) == subtotal`),
overall invoice total positivity ([ADR 0031](0031-non-positive-invoice-total-detection.md)),
and individual line-item positivity ([ADR 0032](0032-non-positive-line-item-detection.md)).
However, the three remaining header monetary fields on `InvoiceExtraction` —
`subtotal`, `tax`, and `discount` — have no individual sign or bound checks.

Furthermore, `_check_invoice_total` in `veridoc.verification.arithmetic` only
runs when all four of `subtotal`, `tax`, `discount`, and `total` are
simultaneously non-null, and `_check_line_items_subtotal` only runs when
`line_items` is non-empty and every line item has a non-null `total_price`. As a
result, three distinct classes of financial and extraction defects currently
evade verification and receive an unearned `clear` verdict:

1. **Non-positive subtotals (`subtotal <= 0`)** — On a commercial invoice, the
   pre-tax, pre-discount `subtotal` represents the aggregate gross value of goods
   or services supplied and must be strictly positive (`subtotal > 0`). When
   `line_items` is empty or has unextracted totals, or when `tax` or `discount`
   is omitted (`None`), an invoice with `subtotal <= 0` and `total > 0` passes
   every existing rule. Even when all four header fields are present, an invoice
   with `subtotal = 0.00, tax = 50.00, discount = 0.00, total = 50.00` (a
   tax-only charge with zero base) or `subtotal = -50.00, tax = 100.00,
   discount = 0.00, total = 50.00` satisfies `subtotal + tax - discount == total`
   and `total > 0`, clearing without review.
2. **Negative tax amounts (`tax < 0`)** — While a zero tax amount (`tax == 0`)
   is normal for tax-exempt, zero-rated, B2B reverse-charge, or export invoices,
   a commercial invoice cannot specify a negative sales tax, VAT, or GST
   liability (`tax < 0`). Under VAT/GST and sales-tax compliance rules, tax
   reductions require a credit note or tax adjustment document. An invoice with
   `subtotal = 100.00, tax = -15.00, discount = 0.00, total = 85.00` (or with
   `discount = None`) currently passes arithmetic and total positivity checks,
   allowing unauthorized embedded tax credits, withholding-tax confusion, or OCR
   hyphen/minus-sign artifacts (`Tax - 15.00` parsed as `-15.00`) to clear
   automatically.
3. **Invalid discount amounts (`discount < 0` or `discount > subtotal`)** — In
   Veridoc's canonical header equation (`subtotal + tax - discount == total`),
   `discount` is an unsigned deduction magnitude (`discount >= 0`). While
   `discount == 0` is valid, a negative `discount` (`discount < 0`)
   mathematically adds to the invoice total (`subtotal + tax - (-discount)`),
   acting either as an unauthorized hidden surcharge disguised as a discount or
   as an unnormalized sign extracted from a printed `Discount: -10.00` line. In
   addition, when `subtotal > 0` and `discount > 0`, a discount exceeding 100%
   of the pre-tax subtotal (`discount > subtotal`) produces a negative net
   pre-tax base (`subtotal - discount < 0`), indicating an embedded rebate offset
   exceeding the invoice value or an OCR column-transposition error.

## Decision

Phase 26 adds three `FindingType` literals (`non_positive_subtotal`,
`negative_tax`, and `invalid_discount`) in `veridoc.verification.models` and
pure deterministic functions in `veridoc.verification.header_amounts`:

1. **`check_non_positive_subtotal(invoice)`**:
   - Inspects `invoice.subtotal`. Returns `[]` when `subtotal is None` or
     `subtotal > Decimal(0)`.
   - When `subtotal <= Decimal(0)`, returns one `non_positive_subtotal` finding
     with `comparison_source="invoice_fields"`,
     `deterministic_rule="invoice.subtotal > 0"`,
     `observed_value=str(invoice.subtotal)`, and `expected_value="> 0.00"`.
   - Severity is `high` for `subtotal < Decimal(0)` and `medium` for
     `subtotal == Decimal(0)`, matching the severity model of
     `non_positive_invoice_total` ([ADR 0031](0031-non-positive-invoice-total-detection.md)).
   - `details` includes `"field": "subtotal"`, `"subtotal": str(invoice.subtotal)`,
     `"is_zero"`, `"is_negative"`, and `"currency"` when present.
2. **`check_negative_tax(invoice)`**:
   - Inspects `invoice.tax`. Returns `[]` when `tax is None` or
     `tax >= Decimal(0)` (zero tax is explicitly permitted).
   - When `tax < Decimal(0)`, returns one `high`-severity `negative_tax` finding
     with `comparison_source="invoice_fields"`,
     `deterministic_rule="invoice.tax >= 0"`,
     `observed_value=str(invoice.tax)`, and `expected_value=">= 0.00"`.
   - `details` includes `"field": "tax"`, `"tax": str(invoice.tax)`,
     `"is_negative": True`, and `"currency"` when present.
3. **`check_invalid_discount(invoice)`**:
   - Inspects `invoice.discount`. Returns `[]` when `discount is None` or when
     `discount >= Decimal(0)` and (if `subtotal is not None and subtotal > Decimal(0)`)
     `discount <= subtotal`.
   - When `discount < Decimal(0)`, returns one `high`-severity `invalid_discount`
     finding with `comparison_source="invoice_fields"`,
     `deterministic_rule="invoice.discount >= 0"`,
     `observed_value=str(invoice.discount)`, `expected_value=">= 0.00"`, and
     `details` including `"field": "discount"`, `"discount": str(invoice.discount)`,
     `"reason": "negative_discount"`, `"is_negative": True`, and `"currency"` when
     present.
   - When `discount > Decimal(0)` and `invoice.subtotal is not None` and
     `invoice.subtotal > Decimal(0)` and `discount > invoice.subtotal`, returns
     one `high`-severity `invalid_discount` finding with
     `comparison_source="invoice_fields"`,
     `deterministic_rule="invoice.discount <= invoice.subtotal"`,
     `observed_value=str(invoice.discount)`,
     `expected_value=f"<= {invoice.subtotal}"`, and `details` including
     `"field": "discount"`, `"discount": str(invoice.discount)`,
     `"subtotal": str(invoice.subtotal)`, `"reason": "discount_exceeds_subtotal"`,
     `"is_negative": False`, and `"currency"` when present.
4. **`check_header_amounts(invoice)`**:
   - Composes `check_non_positive_subtotal`, `check_negative_tax`, and
     `check_invalid_discount` in deterministic order and is invoked by
     `VerificationService.verify()`.

## Alternatives considered

- *Flag `tax == 0` or `discount == 0` as medium-severity anomalies.*
  Rejected: Unlike `total` and `subtotal`, zero tax (`0.00`) is standard on
  tax-exempt, zero-rated, B2B reverse-charge, and export invoices, and zero
  discount (`0.00`) is standard on undiscounted invoices. Flagging zero tax or
  zero discount would generate systematic false positives.
- *Combine all three checks under a single `FindingType`.*
  Rejected: Separate `FindingType` identifiers (`non_positive_subtotal`,
  `negative_tax`, `invalid_discount`) give human reviewers, audit exports, and
  evaluation confusion matrices unambiguous attribution for which header
  invariant failed.
- *Enforce an upper percentage bound on `tax / subtotal`.*
  Rejected: Consumption and excise tax rates vary across jurisdictions and
  product categories; enforcing a hardcoded tax rate cap would violate YAGNI and
  cause false positives on legitimate high-duty invoices.

## Consequences

- Invoices with non-positive subtotals, negative tax amounts, negative
  discounts, or discounts exceeding a positive subtotal are deterministically
  flagged and routed to `review_required`.
- `FindingType` expands by `"non_positive_subtotal"`, `"negative_tax"`, and
  `"invalid_discount"` without requiring any database schema migration or API
  contract breaking change.
