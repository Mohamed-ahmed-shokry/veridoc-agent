# 0039: Required invoice field completeness verification

## Status

Accepted

## Context

Veridoc's deterministic verification rules are individually conditional on the
fields they evaluate. `check_duplicate_invoice_number` returns no finding when
`invoice_number` is `None`. `check_invoice_staleness`,
`check_future_invoice_date`, `check_payment_terms_due_date`, and
`check_excessive_due_date_window` return no finding when the dates they need are
missing. `check_non_positive_invoice_total` and the arithmetic checks return no
finding when `total` is `None`. Same-currency historical and line-item
comparisons silently filter out invoices whose `currency` is `None`.

As a result, a sparse extraction—including an empty invoice whose
`document_type` is `"invoice"`—can satisfy every check vacuously and receive an
automated `clear` verdict even though the facts required to post or audit it are
absent. This is the same class of unearned-clear risk that Phases 31 and 32
addressed for document type and declared extraction uncertainty, but it was
never addressed for field presence itself.

The following four fields are required for a genuinely verifiable invoice:

- `invoice_number`: vendor-scoped identity for duplicate detection, review
  evidence, and AP posting;
- `invoice_date`: anchor for staleness, future-date, payment-term, and
  credit-window rules;
- `currency`: unit of every monetary amount and the key for historical
  comparison;
- `total`: the payable amount evaluated by positivity, arithmetic, purchase
  order ceiling, and historical-outlier rules.

Vendor identity is excluded because missing vendor identity already produces a
dedicated `insufficient_history` finding and a vendor-resolution result.
`due_date`, `payment_terms`, `subtotal`, `tax`, `discount`, and line items are
excluded because they are legitimately optional on many commercial invoices.

## Decision

Phase 33 adds deterministic required-field completeness verification:

1. **`missing_required_field` finding type**:
   - Added to `FindingType` in `veridoc.verification.models`.
   - Comparison source: `"invoice_fields"`.
   - One finding per absent required field, emitted in the fixed order
     `invoice_number`, `invoice_date`, `currency`, `total`.
   - Deterministic rule: `"invoice.<field> is not None"`.
   - Severity: `"high"` for `invoice_number` and `total`; `"medium"` for
     `invoice_date` and `currency`.
   - `observed_value=None`; `expected_value` names the required field.
   - Structured details: `{"field": "<field name>"}`.

2. **`REQUIRED_INVOICE_FIELDS` constant** in
   `veridoc.verification.completeness`:
   - Immutable ordered declaration of field name, severity, and description so
     the rule table is data rather than scattered conditionals.

3. **`check_required_fields(invoice)` pure function**:
   - Returns `[]` when every required field is present.
   - Returns one finding per absent required field without mutating the input.

4. **Service integration**:
   - `VerificationService.verify()` calls `check_required_fields` before every
     field-dependent rule, so the missing-field evidence is always reported
     first and completeness cannot depend on another rule running.

## Alternatives Considered

1. **Make each existing rule emit its own missing-field finding**:
   - *Rejected*: it duplicates findings, couples completeness to each rule's
     applicability conditions, and still leaves vacuously-clear paths for rules
     that are not wired for a given field.
2. **Require every `InvoiceExtraction` field**:
   - *Rejected*: many fields are legitimately optional (`due_date`,
     `payment_terms`, `subtotal`, `tax`, `discount`, line items), so requiring
     them would create systematic false positives.
3. **Reject sparse extractions at the extraction boundary**:
   - *Rejected*: verification owns trust decisions, and a rejected extraction
     would bypass the immutable review snapshot and evidence trail. The
     document-intelligence workflow requires reviewable, accounted-for
     findings.
4. **Emit one aggregate `incomplete_invoice` finding**:
   - *Rejected*: one finding per field preserves structured, field-addressable
     evidence for reviewers, explanation rendering, and auditor bundles.

## Consequences

- Sparse and empty invoice extractions can no longer receive an unearned
  `clear` verdict.
- Reviewers see exactly which required field is absent, with a stable field
  identifier for console filtering and evidence export.
- The rule is pure, deterministic, and preserves input immutability like every
  other verification rule.
- Extraction schemas, persistence, prompts, and evaluation manifests are
  unchanged.
