# 0023: Deterministic vendor and bank reconciliation rules

## Status

Accepted

## Context

The primary goal of invoice reconciliation is deciding whether extracted document
data can be trusted. Invoice redirection fraud—where an attacker submits a legitimate-looking
invoice from a known vendor but replaces the remit-to bank account number with an attacker-controlled
account—is the single largest vector of financial loss in enterprise accounts payable.
Similarly, processing invoices from unregistered suppliers or vendors flagged as suspended
violates procurement governance.

## Decision

Phase 12 introduces four deterministic verification rules targeting vendor identity
and payment integrity:

1. `unregistered_vendor`:
   - Triggered when the entity resolution engine cannot resolve the extracted vendor
     to any registered vendor in the master registry.
   - Severity: `medium` (or `high` when configured).
   - Prevents unvetted or shadow supplier disbursements.

2. `suspended_vendor`:
   - Triggered when the resolved vendor entity has status `suspended` or `inactive`.
   - Severity: `high`.
   - Halts processing for blacklisted or blocked suppliers pending compliance investigation.

3. `vendor_bank_account_mismatch`:
   - Triggered when the extracted invoice contains remit-to banking coordinates
     (IBAN or account number) that do not match any verified bank account registered
     to the resolved vendor entity.
   - Severity: `high`.
   - Flags potential invoice redirection / business email compromise (BEC) fraud.

4. `vendor_tax_id_mismatch`:
   - Triggered when the extracted invoice declares a tax/VAT number that differs from
     the official tax registration numbers on file for the resolved vendor entity.
   - Severity: `high`.
   - Detects fraudulent or misattributed vendor billing.

All four rules populate `ComparisonSource.vendor_registry` and generate structured
`VerificationFinding` objects that factor into deterministic verdict calculation.

## Alternatives considered

- Soft informational warnings for bank account mismatches (rejected: bank account
  redirection is a critical fraud signal requiring human intervention).
- Automated payment blocking or cancellation (rejected: Veridoc derives verification
  verdicts and review requirements; human reviewers make terminal decisions in Phase 9).

## Consequences

Veridoc now directly detects invoice payment fraud and unauthorized vendor billing,
significantly improving the trustworthiness of reconciled invoice data.
