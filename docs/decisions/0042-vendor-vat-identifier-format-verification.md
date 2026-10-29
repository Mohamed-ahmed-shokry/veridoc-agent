# 0042: Vendor VAT identifier format verification

## Status

Accepted

## Context

Phase 35 (ADR 0041) verifies the structure of IBAN-shaped remit-to accounts
without reference data. The extracted `vendor_tax_id` has the same exposure:
the registry tax-id rule only runs for a resolved vendor with registered tax
identifiers, so for unregistered vendors a structurally impossible VAT number
passes every deterministic rule. OCR commonly drops or substitutes characters
in long identifiers, and fabricated identifiers rarely respect the national
structure.

European VAT numbers start with a country prefix and have a published
structure per country (length and character classes). Verifying that structure
needs no reference data and no network access.

## Decision

Phase 36 adds `check_tax_id_format(invoice)` in
`veridoc.verification.tax_id`:

1. **Normalization:** reuse `normalize_tax_id`, so spaces, hyphens, dots, and
   case are ignored exactly as in vendor matching.
2. **Recognized prefixes:** only identifiers whose first two characters appear
   in the bundled country structure table are evaluated. Identifiers with any
   other prefix (domestic or non-European schemes) produce no finding. The
   table covers the EU member state prefixes (using `EL` for Greece), `GB`,
   and `XI`.
3. **Structure only:** each country has one regular expression for the
   characters after the prefix. Checksum algorithms are out of scope.
4. **Finding:** `invalid_tax_id`, severity `medium`, comparison source
   `invoice_fields`, details
   `{"field": "vendor_tax_id", "tax_id": <normalized>, "country": <prefix>}`.
5. **Wiring:** called from `VerificationService.verify()` after bank account
   verification; no schema, persistence, or API change.

## Alternatives considered

- **Flag every unrecognized identifier.** Rejected: many valid identifiers use
  schemes outside the table, which would create review noise.
- **Checksums per country.** Rejected: large, brittle, and out of scope.
- **High severity.** Rejected: unlike an IBAN, the hand-maintained structure
  table may lag national rule changes, so medium severity limits the cost of a
  false positive while still forcing human review.

## Consequences

- Deterministic, side-effect-free, and independent of the registry.
- An invoice with a recognized-prefix but malformed VAT number now routes to
  `review_required`.
- The structure table must be maintained when national formats change.
