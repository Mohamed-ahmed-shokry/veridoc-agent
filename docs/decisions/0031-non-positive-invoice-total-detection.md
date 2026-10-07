# 0031: Detect non-positive invoice totals

## Status

Accepted

## Context

The verification layer validates internal arithmetic (subtotals, line-item
multiplication, discounts, tax, total equality), temporal validity (future issue
dates, historical staleness, due date ordering), duplicate invoice numbers,
duplicate line items within an invoice, purchase-order authorization ceilings,
and vendor master registry compliance. However, it lacks any validation of the
positivity of the invoice total amount itself.

In commercial accounts payable and document intelligence, an invoice
(`document_type="invoice"`) is an instrument requesting payment for goods or
services delivered. Under standard accounting principles (GAAP, IFRS) and
business controls, a commercial invoice must specify a strictly positive payable
total (`total > 0`).

Two distinct risk patterns produce invoices with non-positive totals:

1. **Negative invoice totals (`total < 0`)** — an invoice specifying a negative
   balance indicates a credit note, debit memo, return adjustment, or refund
   claim. In automated accounts payable reconciliation, processing a negative
   amount under a standard invoice workflow without dedicated credit-note
   authorization and debit-reversal handling corrupts accounts payable ledgers,
   causes erroneous automated payment disbursements or balance offsets, and
   creates an avenue for unauthorized balance manipulation.
2. **Zero invoice totals (`total == 0`)** — an invoice specifying a zero balance
   ($0.00) indicates an operational anomaly: an informational delivery slip,
   pro-forma quote, warranty replacement, or sample receipt erroneously routed as
   a commercial invoice. Alternatively, a zero total is a frequent vision/OCR
   extraction failure mode where the monetary total was blanked, occluded, or
   misparsed as zero. Allowing zero-dollar invoices to pass automatically can
   cause unfulfilled purchase-order line items to be marked as satisfied or
   introduce zero-value vouchers into accounting registers.

Currently, if an extracted invoice has `total <= 0` with consistent internal
arithmetic (for example, `subtotal = -100.00, tax = 0.00, discount = 0.00,
total = -100.00`, or all zeros), `check_arithmetic` passes. Historical staleness
explicitly excludes non-positive totals (`total <= 0`), future-date checks only
evaluate dates, duplicate checks only evaluate identifiers, and purchase-order
checks pass because a non-positive amount is naturally less than or equal to an
authorized purchase order ceiling. The invoice thus evades every verification check
and receives an unearned `clear` processing verdict. Flagging non-positive invoice
totals for human review closes this critical financial verification gap.

## Decision

Phase 24 introduces a `non_positive_invoice_total` finding type and a pure
deterministic function `check_non_positive_invoice_total` in
`veridoc.verification.invoice_totals`:

- The rule inspects `invoice.total`. If `invoice.total` is absent (`None`), the
  check returns an empty list, preserving the property that missing optional
  fields do not generate false arithmetic anomalies.
- If `invoice.total > Decimal(0)`, the invoice is strictly positive and the check
  returns an empty list.
- When `invoice.total <= Decimal(0)`, the rule generates exactly one
  `non_positive_invoice_total` finding.
- Severity is differentiated based on financial risk:
  - **`high` severity** for **negative totals** (`total < Decimal(0)`): A negative
    invoice total represents a credit memo or refund request masquerading as a
    standard invoice, posing an immediate risk of ledger distortion or
    unauthorized debit processing.
  - **`medium` severity** for **zero totals** (`total == Decimal(0)`): A zero total
    warrants human review to verify whether the document is a zero-value voucher,
    pro-forma document, or extraction artifact.
- `comparison_source` is `"invoice_fields"`.
- `deterministic_rule` is `"invoice.total > 0"`.
- `observed_value` is `str(invoice.total)`, and `expected_value` is `"> 0.00"`.
- `details` includes `"field": "total"`, `"total": str(invoice.total)`,
  `"is_zero": True/False`, `"is_negative": True/False`, and `"currency"` if
  extracted.

`VerificationService.verify()` calls `check_non_positive_invoice_total`
alongside `check_arithmetic`, `check_duplicate_line_items`,
`check_invoice_staleness`, and `check_future_invoice_date`. No database migration,
repository changes, or external service dependencies are required.

## Alternatives considered

- *Merge the check into `_check_invoice_total` in `arithmetic.py`.*
  Rejected: `arithmetic.py` validates mathematical equality among extracted
  relational fields (`subtotal + tax - discount == total`). Positivity of the
  payable total is an accounts payable domain integrity rule, not an equation
  equality failure. Placing it in a dedicated module maintains modularity and
  matches the patterns of `staleness.py`, `future_dates.py`, and
  `duplicate_line_items.py`.
- *Treat both zero and negative totals with uniform severity.*
  Rejected: Negative invoices pose direct ledger manipulation and payment
  reversal risks, warranting `high` severity. Zero-dollar invoices often
  represent benign operational vouchers (e.g. warranty service or pro-forma
  slips) that warrant human review (`medium` severity) rather than severe
  condemnation.
- *Flag missing totals (`total is None`) under this rule.*
  Rejected: In the Veridoc extraction schema, document fields are nullable when
  unextracted or occluded. Missing fields are an extraction completeness concern
  rather than an explicit non-positive value finding. Flagging absent totals
  under this rule would conflate extraction omissions with extracted non-positive
  amounts.

## Consequences

Invoices specifying zero or negative totals produce actionable findings that
route them to human review (`review_required`). `FindingType` gains
`"non_positive_invoice_total"`. Processing schemas remain backwards-compatible,
and no database migrations or external dependencies are required.
