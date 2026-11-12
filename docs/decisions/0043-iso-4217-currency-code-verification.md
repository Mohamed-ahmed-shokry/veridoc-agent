# 0043: ISO 4217 currency code verification

## Status

Accepted

## Context

In Version 1 invoice extraction (`InvoiceExtraction`), the `currency` field is
constrained only by the generic regex pattern `^[A-Z]{3}$`. Consequently, any
arbitrary three-letter uppercase string (such as `XYZ`, `INV`, `TOT`, or `FOO`)
is admitted as a syntactically valid currency. In Phase 33 (ADR 0039), currency
completeness is enforced as a required header field because downstream monetary
comparisons and historical baselines are partitioned by currency.

However, an invoice whose currency code does not correspond to any recognized
international standard currency poses significant payment and accounting risks:
it cannot be settled through automated clearing houses (ACH), wire transfers,
or ERP accounts payable ledgers, and cannot be matched against purchase orders
or historical spend. Furthermore, vision and OCR models frequently hallucinate
abbreviations (e.g. `DLR` instead of `USD`) or capture adjacent header words as
currencies.

The International Organization for Standardization publishes ISO 4217, the
authoritative standard specifying three-letter alphabetic currency codes for
active legal tenders and international settlement units (such as `USD`, `EUR`,
`GBP`, `JPY`, `CAD`, `AUD`, `CHF`). Verifying extracted currency against this
authoritative set requires no external network access or reference data.

## Decision

Phase 37 adds `check_currency_code(invoice)` in
`veridoc.verification.currency`:

1. **Authoritative Table:** Maintain `ISO_4217_CURRENCY_CODES` as an immutable
   `frozenset[str]` containing standard active alphabetic currency codes.
2. **Normalization:** Strip leading and trailing whitespace and normalize to
   uppercase. If `invoice.currency` is absent (`None`) or empty, return `[]`
   (omitted currency is handled by `missing_required_field`).
3. **Validation:** If the normalized currency code is not in
   `ISO_4217_CURRENCY_CODES`, return one `invalid_currency` finding.
4. **Finding Details:**
   - Finding type: `invalid_currency`
   - Severity: `medium`
   - Comparison source: `invoice_fields`
   - Deterministic rule: `currency in ISO 4217 active alphabetic codes`
   - Details: `{"field": "currency", "currency": <normalized_code>}`
5. **Wiring:** Called from `VerificationService.verify()` immediately after VAT
   identifier format verification. No schema, persistence, or external API change.

## Alternatives considered

- **High severity.** Rejected: while an unrecognized currency prevents automated
  payment execution, assigning `medium` severity ensures review escalation
  without drowning out critical security findings such as remit-to bank account
  tampering (`invalid_bank_account`).
- **Dynamic FX rate lookup / conversion.** Rejected: out of scope for Version 1;
  requires external network connectivity, live market feeds, and stateful currency
  conversion logic.
- **Support obsolete or cryptocurrency symbols.** Rejected: ISO 4217 fiat and
  settlement currencies are the accepted standard for commercial enterprise AP.

## Consequences

- Deterministic, side-effect-free, and requires zero network access.
- Invoices carrying hallucinated, misspelled, or fabricated currency codes route
  to `review_required`.
- The ISO 4217 currency table is bundled locally as part of the core package.
