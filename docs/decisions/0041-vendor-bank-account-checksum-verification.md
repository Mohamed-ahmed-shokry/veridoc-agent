# 0041: Vendor bank account checksum verification

## Status

Accepted

## Context

The vendor registry rules compare an extracted
`vendor_bank_account` against registered accounts. They are silent when the
vendor is unregistered, has no registered account, or the registry is not
configured. In those cases a remit-to account that is structurally impossible
passes every deterministic rule:

- OCR frequently misreads a single digit of a long IBAN; the corrupted value is
  then not a real account at all.
- A fabricated account is rarely constructed with a valid checksum.

IBANs carry a built-in integrity check (ISO 13616): a country-specific length
and an ISO 7064 mod-97-10 checksum. Verifying it needs no reference data and no
jurisdiction thresholds, and a failure is a certain structural defect rather
than a statistical suspicion.

## Decision

Phase 35 adds `check_bank_account_checksum(invoice)` in
`veridoc.verification.bank_account`:

1. **Normalization:** reuse `normalize_bank_account` so spaces, hyphens, dots,
   and case are ignored exactly as in vendor matching.
2. **IBAN-shaped detection:** a value is IBAN-shaped when it matches
   `^[A-Z]{2}[0-9]{2}[A-Z0-9]+$` and its country code appears in the bundled
   IBAN length table. Anything else (domestic account numbers, free text,
   unknown prefixes) is out of scope and produces no finding, because the
   rule must not penalize legitimate non-IBAN remittance details.
3. **Checks:** a length differing from the country length yields
   `reason="length"`; otherwise a failed mod-97 remainder yields
   `reason="checksum"`. At most one finding is emitted.
4. **Finding:** `invalid_bank_account`, severity `high`, comparison source
   `invoice_fields`, details
   `{"field": "vendor_bank_account", "account": <normalized>, "reason": ...}`.
5. **Wiring:** called from `VerificationService.verify()` after line-item
   completeness; no schema, persistence, or API change.

## Alternatives considered

- **Flag every non-IBAN account.** Rejected: many domestic payments use
  national formats, which would create review noise on legitimate invoices.
- **Per-country BBAN checksums.** Rejected: large, brittle, and out of scope.
- **Medium severity.** Rejected: the account is provably invalid, and a
  corrupted remit-to account directly risks misdirected payment.

## Consequences

- Deterministic, side-effect-free, and independent of the registry.
- A fixture or real invoice with an IBAN-shaped but invalid account now routes
  to `review_required`.
- The country-length table must be maintained if the IBAN registry changes.
