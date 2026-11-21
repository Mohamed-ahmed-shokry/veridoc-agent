# 0051: Vendor name and registry consistency verification

## Status

Accepted

## Context

In Veridoc's multi-attribute vendor entity resolution (`veridoc.vendors.resolution.resolve_vendor`), exact tax registration ID (`exact_tax`) and exact bank account / IBAN (`exact_bank`) matches take priority over name matching. While this ensures reliable resolution when a vendor's trading name differs slightly from its legal name, it introduces a blind spot: if an invoice presents a registered vendor's tax ID or bank account alongside an unrelated or spoofed `vendor_name` (e.g., `"Shell Consulting LLC"` instead of `"Acme Corporation Ltd"`), `resolve_vendor` still resolves to that vendor and `check_vendor_registry` previously emitted no name-mismatch finding.

The same blind spot can occur when `vendor_identifier` resolves to a vendor via `canonical_key` or `aliases` while `invoice.vendor_name` states a materially different supplier name.

## Decision

1. **New Finding Type**: Add `vendor_name_mismatch` to `FindingType` in `veridoc.verification.models`.
2. **Pure Verification Rule**: Implement `check_vendor_name(resolution, invoice, vendor, *, fuzzy_threshold=0.85)` in `veridoc.verification.vendor_rules`, reusing `derive_canonical_vendor_key` and `calculate_token_similarity` from `veridoc.vendors`.
3. **Exclusion Paths**: Emit `[]` when `resolution` is `None` or unresolved, `vendor` is `None`, `invoice.vendor_name` is `None`/blank or canonicalizes to empty, or `invoice.vendor_name` matches `vendor.canonical_key`, any canonicalized alias in `vendor.aliases`, or achieves token similarity `>= fuzzy_threshold` against `vendor.legal_name` or any alias.
4. **Triggering Path**: Emit one `medium`-severity `vendor_name_mismatch` finding with `comparison_source="vendor_registry"`, `observed_value=invoice.vendor_name`, `expected_value=vendor.legal_name`, and structured `details` (`extracted_vendor_name`, `resolved_legal_name`, `vendor_id`, `best_similarity_score`).
5. **Registry Integration**: Invoke `check_vendor_name(resolution, invoice, vendor)` inside `check_vendor_registry()`, routing mismatched invoices to `review_required`.

## Consequences

- **Positive**: Material contradictions between extracted `vendor_name` and tax/bank/ID-resolved vendor master records are deterministically surfaced for human review.
- **Neutral**: Legitimate legal-name variants, registered aliases, and token-reordered names (`>= 0.85` similarity) continue to pass cleanly.
- **Negative**: None; zero changes to `resolve_vendor` priority ordering or persistence schemas.
