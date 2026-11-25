# 0054: Potential duplicate invoice detection

## Status

Accepted

## Context

Veridoc detects exact and normalized duplicate invoice numbers within a vendor's history via `check_duplicate_invoice_number` (ADR 0026). However, accounts-payable double billing frequently occurs under a different invoice number: a supplier resubmits an invoice with an appended suffix (e.g., `INV-1001-R`), re-exports a document with a fresh sequence number, or OCR misreads a character in the invoice number (e.g., `INV-1001` read as `INV-1007`). When the resubmitted invoice shares the same vendor, exact `invoice_date`, `currency`, and positive `total`, neither `check_duplicate_invoice_number` nor statistical total checks flag the collision if the total lies within the vendor's normal range.

## Decision

1. **New Finding Type**: Add `potential_duplicate_invoice` to `FindingType` in `veridoc.verification.models`.
2. **Exact-Key Fingerprint Match**: Implement `check_potential_duplicate_invoice(invoice, history)` in `veridoc.verification.repository_checks`, comparing `(vendor_key, invoice_date, normalized_currency, total)` against prior invoices in `history`.
3. **Exclusion Paths**: Emit `[]` when `vendor_key`, `invoice_date`, `currency`, or `total` is absent, when `total <= 0`, or when no historical invoice matches the exact date, normalized currency, and total.
4. **Deduplication with Exact Invoice-Number Check**: Skip any historical record whose canonicalized `invoice_number` matches `normalize_invoice_number(invoice.invoice_number)` (when `invoice.invoice_number` is present), because exact/normalized number duplicates are already owned and flagged at `severity="high"` by `check_duplicate_invoice_number`.
5. **Triggering Path**: Emit one `medium`-severity `potential_duplicate_invoice` finding with `comparison_source="invoice_register"`, `observed_value` formatted as `"{date} | {currency} {total}"`, `expected_value="unique vendor invoice for this date, currency, and total"`, and structured `details` (`vendor_key`, `invoice_date`, `currency`, `total`, `observed_invoice_number`, `existing_invoice_number`).
6. **Service Integration**: Invoke `check_potential_duplicate_invoice(invoice, history)` in `VerificationService.verify()` immediately after `check_duplicate_invoice_number(invoice, history)`, routing potential duplicates to `review_required`.

## Alternatives Considered

- **Multi-day date window (e.g., +/- 3 days) or amount tolerance**: Rejected because recurring or split commercial shipments on nearby dates with similar amounts would generate false positives. Exact date + exact currency + exact positive total keeps precision high while catching true same-day resubmissions and OCR invoice-number misreads.
- **High severity (`severity="high"`)**: Rejected because legitimate same-day, same-amount invoices with distinct invoice numbers can occasionally occur (e.g., two separate standard deliveries). `medium` severity still routes deterministically to `review_required` while signaling to reviewers that the match is circumstantial rather than an identical invoice number.

## Consequences

- **Positive**: Resubmitted invoices with altered or OCR-corrupted invoice numbers on the same date for the same amount are deterministically flagged for human review instead of clearing vacuously.
- **Neutral**: Exact duplicate invoice numbers continue to emit only `duplicate_invoice_number` (`high`), avoiding redundant findings.
- **Negative**: None; pure deterministic function over already-loaded vendor history with zero schema or repository changes.
