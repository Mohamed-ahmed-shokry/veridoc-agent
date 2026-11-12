# 0047: Cross-field vendor country and bank account consistency verification

## Status

Accepted

## Context

In financial operations, accounts payable (AP) fraud, and business email compromise (BEC) attacks,
invoice redirection represents one of the highest-loss attack vectors. In a typical invoice redirection
scenario, an attacker or compromised vendor submits an invoice featuring genuine supplier credentials
and tax identification (e.g. a valid German `DE` or French `FR` VAT number), but alters the payment remittance
details so that wire transfers are routed to an offshore or foreign bank account in an unrelated country
(e.g. Cyprus `CY` or Malta `MT`).

Veridoc's prior phases introduced:
1. `check_bank_account_checksum` in Phase 35 ([ADR 0041](0041-vendor-bank-account-checksum-verification.md)), which validates that an extracted IBAN conforms to ISO 13616 country lengths and passes the ISO 7064 mod-97 checksum.
2. `check_tax_id_format` in Phase 36 ([ADR 0042](0042-vendor-vat-identifier-format-verification.md)), which validates that an extracted European VAT number matches national formatting rules.
3. `check_vendor_registry` in Phase 12 ([ADR 0023](0023-deterministic-vendor-and-bank-reconciliation-rules.md)), which compares extracted bank accounts and tax IDs against pre-registered vendor master records.

However, when an invoice originates from a new or un-enrolled vendor (where no master reference record exists
in SQLite), both fields are evaluated independently. An invoice with a valid German VAT number (`DE123456789`)
and a valid Cyprus IBAN (`CY17002001280000001201234567`) passes both Phase 35 and Phase 36 with zero findings,
potentially receiving an unearned `clear` verdict if totals and dates align.

Because European VAT numbers explicitly encode the vendor's tax jurisdiction in the first two characters,
and ISO 13616 IBANs explicitly encode the financial institution's country in the first two characters,
a deterministic cross-field comparison can be made without external network calls or database dependencies.

## Decision

1. **New Finding Type**: Introduce `tax_id_bank_country_mismatch` in `veridoc.verification.models.FindingType` with `severity="high"`.
2. **Pure Deterministic Rule**: Implement `check_tax_id_bank_country_consistency(invoice: InvoiceExtraction) -> list[VerificationFinding]` in `veridoc.verification.country_consistency`.
   - Extract and normalize `vendor_tax_id` and `vendor_bank_account` using existing normalizers (`normalize_tax_id`, `normalize_bank_account`).
   - Identify the tax country prefix from the first two characters of the normalized tax ID against `VAT_STRUCTURES`.
   - Identify the bank country prefix from the first two characters of the normalized IBAN against `IBAN_COUNTRY_LENGTHS`.
   - If either field is absent, blank, or has an unrecognized country prefix, emit no finding (deferred to individual checks).
   - Compare the two country codes, supporting recognized geographic equivalence:
     - `EL` (Greek VAT code) <-> `GR` (Greek ISO country / IBAN code).
     - `XI` (Northern Ireland VAT code under Brexit protocol) <-> `GB` (United Kingdom IBAN code).
   - If the canonical country codes do not match, emit one `high`-severity finding with:
     - `comparison_source="invoice_fields"`
     - `deterministic_rule="tax_country == bank_country"`
     - `details={"tax_country": tax_country, "bank_country": bank_country, "vendor_tax_id": tax_id, "vendor_bank_account": bank_account}`
3. **Pipeline Integration**: Integrate `check_tax_id_bank_country_consistency` into `VerificationService.verify()` immediately following `check_tax_id_format`.
4. **Immutability**: Input invoice extractions remain strictly immutable.

## Consequences

- Invoices with mismatched VAT and IBAN country codes (e.g. `FR` tax ID with `CY` IBAN) are immediately flagged with `high` severity, routing the invoice to human review (`review_required`).
- Domestic or non-European accounts without standard ISO 2-letter prefixes pass through safely without false alarms.
- Known legitimate cross-border prefix variations (`EL`/`GR` and `XI`/`GB`) are handled gracefully without false alarms.
