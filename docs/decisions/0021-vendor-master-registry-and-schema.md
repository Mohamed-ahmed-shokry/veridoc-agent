# 0021: Vendor master registry and schema

## Status

Accepted

## Context

To date, Veridoc has relied exclusively on string normalization (`normalize_vendor_key`)
to identify vendors across historical invoices and purchase orders. In real-world
accounts payable workflows, vendor identity is multi-faceted: a vendor has a registered
legal name, trade names or aliases, tax/VAT registration identifiers, and approved
remit-to bank accounts (IBAN or local account numbers). Without an authoritative
vendor master registry, the system cannot verify vendor legitimacy, handle common
trading aliases, or reconcile payment coordinates.

## Decision

Phase 12 introduces an authoritative Vendor Master Registry persisted in the
local SQLite reference database:

1. Schema Migration:
   - Migration 5 adds `vendors`, `vendor_aliases`, `vendor_bank_accounts`, and
     `vendor_tax_ids` tables to the reference SQLite database;
   - `vendors` tracks server `id`, unique `vendor_id`, `legal_name`, `canonical_key`,
     lifecycle `status` (`active`, `suspended`, `inactive`), plus full provenance
     columns (`record_id`, `source`, `external_id`, `created_at`, `updated_at`,
     `retention_until`);
   - `vendor_aliases` stores approved trade names and aliases linked by foreign key;
   - `vendor_bank_accounts` stores verified remit-to coordinates (account number, bank
     code, IBAN, routing number) with unique vendor/account constraints;
   - `vendor_tax_ids` stores official tax registration numbers (VAT, EIN, CRN) and
     country codes.

2. Repository and Administration Boundary:
   - `VendorRepository` defines read and lookup operations for invoice processing;
   - `VendorAdminRepository` defines bounded CRUD and atomic import operations;
   - HTTP routes under `/admin/reference-data/vendors` enforce loopback caller isolation
     (ADR 0013) and Bearer token authentication (ADR 0006);
   - Bulk JSON import (`POST /admin/reference-data/import`) supports atomic vendor
     records with dry-run and conflict policies.

## Alternatives considered

- Storing vendor master records in a separate database file (rejected: complicates
  atomic backup/restore and transactions without operational benefit).
- Integrating external remote ERP vendor directories in v1 (rejected: violates YAGNI
  and requires remote network dependencies).
- Retaining string-only normalization without a master registry (rejected: unable to
  verify bank details or detect invoice redirection fraud).

## Consequences

Reference data now provides an authoritative source of truth for vendor entities,
aliases, tax IDs, and bank accounts. Migrations remain forward-only and fully
backward-compatible with existing invoice and purchase-order records.
