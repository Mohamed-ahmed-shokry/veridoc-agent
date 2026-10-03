# 0029: Detect future-dated invoices by issue date

## Status

Accepted

## Context

The verification layer checks internal consistency (arithmetic, relative dates
such as invoice date versus due date), vendor-history anomalies (totals,
line-item prices, duplicates, payment terms), purchase-order authorization,
vendor-registry compliance, and historical staleness (ADR 0028). However, the
inverse temporal risk remains undetected: an invoice whose issue date lies in
the future relative to the current processing date.

Two primary risk patterns produce future-dated (post-dated) invoices:

1. **Financial fraud and accounting cutoff manipulation** — an issuer
   post-dates an invoice to manipulate fiscal cutoffs, prematurely book
   revenue in an upcoming accounting period, or attempt advance cash
   disbursements prior to legitimate billing milestones. Under accounting
   standards (GAAP, IFRS) and tax regulations (VAT, GST, sales tax), an
   invoice dated in the future cannot be legally posted to accounts payable or
   claimed for input tax deduction before its tax point / issue date occurs.
2. **Extraction and OCR errors** — automated vision extraction and OCR models
   frequently misinterpret date strings. Prominent failure modes include year
   digit misrecognition (e.g., misreading 2024 as 2029) and day/month
   transposition (e.g., parsing 05/11 as May 11 instead of November 5, which
   may place the extracted date months in the future).

The existing `_check_invoice_dates` rule in `arithmetic.py` checks only that
`invoice_date <= due_date`. If both `invoice_date` and `due_date` are far in the
future, or if `due_date` is omitted, the invoice passes verification with no
findings and derives a `clear` processing verdict. Flagging future-dated
invoices for human review prevents premature automated trust.

## Decision

Phase 22 adds a `future_invoice_date` finding type and a pure deterministic
`check_future_invoice_date` function in `veridoc.verification.future_dates`:

- The rule fires when `invoice_date` is present and strictly greater than the
  reference date (`invoice_date > today`).
- The reference date is injected as a parameter (defaulting to
  `datetime.now(UTC).date()`), keeping the function purely deterministic and
  testable without patching or clock dependencies.
- Severity is `medium` — the future date warrants human review (yielding a
  `review_required` verdict), allowing an operator to inspect whether the
  finding stems from a timezone discrepancy, an extraction error, or fraud.
- `comparison_source` is `"invoice_fields"`, and `deterministic_rule` is
  `"invoice_date <= today"`.
- Invoices with a purchase order are not excluded: unlike historical staleness,
  where a long-running contract PO explains an old invoice date, a purchase
  order never authorizes billing in the future.
- Zero-total, negative-total, and missing-total invoices are not excluded: an
  invoice or credit memo dated in the future is invalid regardless of amount.

`VerificationService.verify()` calls `check_future_invoice_date` alongside
`check_invoice_staleness`. No database migration, new repository method, or
threshold calibration is required.

## Alternatives considered

- Add a tolerance window (e.g., 1 day for timezone drift).
  Rejected: In strict accounting controls, an invoice dated tomorrow cannot be
  posted to accounts payable today regardless of the vendor's timezone.
  `medium` severity already routes the case to human review rather than
  fatal rejection, allowing operators to approve legitimate timezone drift.
- Merge the check into `_check_invoice_dates` in `arithmetic.py`.
  Rejected: `arithmetic.py` validates internal self-consistency among
  extracted invoice fields (subtotal, tax, discount, total, line items, and
  intra-invoice date ordering). Comparisons against the current wall-clock
  processing date are temporal verification checks and belong in dedicated
  modules alongside `staleness.py`.
- Require `total > 0` before flagging.
  Rejected: A future-dated credit note or zero-amount document represents
  the same legal cutoff violation and OCR error profile as a positive invoice.

## Consequences

Invoices dated in the future now produce a `medium` finding that routes them to
human review. The `FindingType` union gains one literal; `VerificationResult`
and `ProcessingResult` schemas are unchanged; no migration, route, or console
change is needed. The rule is covered by deterministic tests following the
patterns established throughout the verification subsystem.
