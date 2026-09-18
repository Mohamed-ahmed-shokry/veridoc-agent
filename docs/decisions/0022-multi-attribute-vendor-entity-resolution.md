# 0022: Multi-attribute vendor entity resolution

## Status

Accepted

## Context

Invoices presented to accounts payable systems often reference vendors using
imperfect identifiers: legal names may be abbreviated or suffixed differently
(e.g., "Acme Corporation" vs. "Acme Corp Ltd."), invoices may list commercial trade
names ("Acme Logistics") rather than legal registered names, or invoices may
prominently display a national tax/VAT identifier or remit-to bank account number.
A single-attribute naive string match produces high false-negative rates and cannot
resolve ambiguous vendor references.

## Decision

Phase 12 adopts a deterministic, multi-attribute cascading entity resolution engine:

1. Cascading Matching Strategy:
   - Priority 1: Exact Tax/VAT ID Match (`exact_tax` confidence). Official tax registration
     numbers provide the highest deterministic guarantee of entity identity.
   - Priority 2: Exact Bank Account / IBAN Match (`exact_bank` confidence). Remit-to bank
     accounts registered to exactly one vendor provide high identity certainty.
   - Priority 3: Exact Canonical Key or Registered Alias Match (`exact_alias` confidence).
     Exact match against the vendor's canonical slug or registered trade aliases.
   - Priority 4: Bounded Token Set Similarity Match (`fuzzy_name` confidence). Token set
     similarity ratio $\ge 0.85$ between the extracted vendor name and registered vendor
     names/aliases, tolerating word-order shifts and minor punctuation differences.
   - Fallback: Unresolved (`unresolved`). If no candidate meets the threshold or if multiple
     conflicting candidate entities are identified, the resolution returns unresolved.

2. Auditable Resolution Payload:
   - Every invoice resolution produces a structured `VendorResolutionResult` recording:
     `resolved_vendor_id`, `canonical_key`, `confidence`, `score`, `matched_attribute`,
     and current vendor `status` (`active`, `suspended`, `inactive`).
   - The resolution output is embedded in `ProcessingResult` and retained in immutable
     review case snapshots.

## Alternatives considered

- Using an LLM prompt to identify or guess the matching vendor (rejected: non-deterministic,
  unpredictable hallucination risk, high latency, and privacy exposure).
- Levenshtein edit distance alone without tokenization (rejected: fragile to reordered
  words like "Acme Global Solutions" vs. "Solutions Global Acme").
- Exact string matching only (rejected: rejects valid invoices with minor abbreviation
  differences).

## Consequences

Vendor resolution is completely auditable, deterministic, and fast. The resolution
tier and matched attribute are explicitly recorded for review and verification rules.
