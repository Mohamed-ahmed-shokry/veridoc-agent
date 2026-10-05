# 0030: Detect duplicate line items within an invoice

## Status

Accepted

## Context

The verification layer validates arithmetic consistency (subtotals, tax, discounts,
line-item math, totals), temporal dates (future issue dates, stale invoices, due
date ordering), vendor registry compliance, cross-invoice duplicate invoice numbers,
and historical statistics. However, it lacks any intra-invoice check for duplicate
line items.

In accounts payable and invoice processing, duplicate line items represent a major
clerical error and billing fraud pattern:

1. **Double-billing fraud and data entry errors** — an issuer inadvertently or
   intentionally lists the same deliverable, fee, or service multiple times
   on a single invoice. Because the arithmetic engine calculates the subtotal as the
   sum of all line-item totals (`sum(line_item.total_price) == subtotal`), an
   invoice containing duplicated lines will pass arithmetic validation without
   error.
2. **Vision extraction and OCR artifacts** — vision-language models and OCR layout
   engines occasionally re-read table rows, transcribe overlapping bounding boxes,
   or generate duplicate structured line items from repeated headers or page
   transitions.

An invoice with duplicated lines currently passes arithmetic, temporal, and historical
verification, receiving an unearned `clear` processing verdict unless a purchase order
is attached or total outliers are triggered. Detecting duplicate line items within an
invoice prevents automated acceptance of double-billed charges.

## Decision

Phase 23 introduces a `duplicate_line_item` finding type and a deterministic pure
function `check_duplicate_line_items` in `veridoc.verification.duplicate_line_items`:

- The rule inspects `invoice.line_items` and computes each line's comparison key
  using `line_item_key` from `veridoc.verification.line_items`. This canonicalizes
  product identifiers and descriptions by stripping whitespace, collapsing multiple
  spaces, and casefolding.
- Line items with no identifiable key (both `product_identifier` and `description`
  absent or blank) are ignored.
- When two or more line items share the same key, every occurrence after the first
  generates a `duplicate_line_item` finding referencing the index of the first
  occurrence (`duplicate_of_index`).
- Severity is differentiated based on matching depth:
  - **`high` severity** for **exact duplicates** where both `quantity` and
    `unit_price` are present and equal between the duplicate and the initial
    occurrence. Identical line items represent high-confidence double-billing or
    OCR repetition errors.
  - **`medium` severity** for **partial duplicates** where the product or
    description matches but `quantity` or `unit_price` differs (or is omitted).
    In AP operations, split lines may represent multiple delivery batches or
    distinct milestones, warranting human review rather than automatic high-severity
    condemnation.
- `comparison_source` is `"invoice_line_items"`.
- `deterministic_rule` is `"line items within an invoice must be unique by product identifier or description"`.
- Details include the duplicate line index, initial line index, match type
  (`"exact"` or `"partial"`), key, and extracted quantity and unit price.

`VerificationService.verify()` calls `check_duplicate_line_items`. No database migration,
repository change, or external service dependency is required.

## Alternatives considered

- *Merge the check into `_check_line_item_amounts` or `_check_line_items_subtotal` in `arithmetic.py`.*
  Rejected: `arithmetic.py` handles purely mathematical relationships among
  numeric amounts. Semantic uniqueness of line items within an invoice is a line-item
  reconciliation concern that belongs in its own module.
- *Treat all duplicate line keys as `high` severity.*
  Rejected: Suppliers sometimes legitimately split deliveries of the same product
  into separate lines (e.g. 5 units delivered on Monday, 5 units on Friday).
  Setting partial duplicates to `medium` routes them to review without falsely
  labeling routine split entries as severe fraud.
- *Exact verbatim text comparison without normalization.*
  Rejected: Trivial differences in whitespace or letter casing (`Widget A` vs
  `widget   a`) would evade duplicate detection. Reusing `line_item_key` ensures
  consistent canonical comparison across the verification subsystem.

## Consequences

Invoices containing duplicate line items produce actionable findings that route them
to human review (`review_required`). `FindingType` gains `"duplicate_line_item"`.
Processing schemas remain backwards-compatible, and no database migrations are
necessary.
