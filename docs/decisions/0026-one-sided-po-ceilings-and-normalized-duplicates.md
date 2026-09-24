# 0026: Use one-sided PO ceilings and normalized invoice-number identity

## Status

Accepted

## Context

Two verification rules produce systematic false positives while missing
nearby true positives:

1. `check_duplicate_invoice_number` compares the extracted invoice number
   verbatim against stored rows, and rows store the number verbatim. OCR
   and provider output vary spacing, dash shapes, and case (`INV-001`,
   `inv 001`, `INV–001`), so resubmitted invoices evade the check whenever
   their rendering differs by trivia.
2. `check_purchase_order` requires exact equality for PO totals and line
   quantities. Routine partial invoices — billing $2,000 against a $10,000
   PO, or 20 of 100 ordered units — flag high-severity on every submission,
   training operators to ignore PO findings.

## Decision

Phase 16 treats purchase orders as authorization ceilings and invoice
numbers as canonical identities:

- Invoice numbers canonicalize with NFKC normalization, dash-like
  characters folded to hyphen-minus, all whitespace removed, and
  casefolding. Duplicate detection compares the canonical form across the
  vendor history and keeps the `duplicate_invoice_number` type, recording
  both the observed and stored forms. Verbatim-identical invoices behave
  exactly as before.
- PO totals and line quantities become one-sided: invoiced amounts at or
  below the authorized values pass; amounts above flag
  `purchase_order_mismatch`. Unit prices stay exact — price changes have no
  legitimate "partial" reading. The PO line-total comparison is removed:
  with quantities one-sided and unit prices exact, it only re-flags partial
  quantities already accepted.
- A cumulative ceiling sums prior same-currency vendor-history invoices
  referencing the same PO number plus the current total and flags when the
  sum exceeds the PO total, catching split over-billing across partial
  invoices. It reuses the already-loaded vendor history; no new repository
  method, migration, or finding type.
- Missing values still skip (never treated as zero), and cross-currency
  comparisons still require equal currency codes before amounts compare.

## Alternatives considered

- Keep exact PO equality and verbatim duplicate matching.
- Add symmetric tolerances (plus/minus epsilon) around PO amounts.
- Add a new `possible_duplicate_invoice` heuristic type for fuzzy matches.
- Model goods receipts as a third reconciliation leg.

## Consequences

Partial-invoice false positives disappear while over-billing recall is
preserved in every direction: single-invoice excess, line excess, and
cumulative excess all still flag high-severity. The price is a narrower
duplicate definition than full fuzzy matching — reorderings or heavily
rewritten numbers still evade it — documented here as residual risk.
Unit-price strictness is unchanged, so legitimate price updates still
require review. No schema, migration, finding-type, or threshold changes.
