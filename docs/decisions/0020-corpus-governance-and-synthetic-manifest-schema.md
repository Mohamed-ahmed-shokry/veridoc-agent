# 0020: Enforce corpus governance with SHA-256 manifests and synthetic evaluation data

## Status

Accepted

## Context

Evaluating an invoice reconciliation system requires access to representative
documents. Real enterprise invoices contain personally identifiable information
(PII), confidential business pricing, banking coordinates, and proprietary vendor
relationships. Committing real documents or unvalidated downloads into source control
risks data leaks, copyright infringement, and license violations. Furthermore,
untracked or floating evaluation files compromise reproducibility if files are
modified, renamed, or corrupted.

## Decision

Phase 11 enforces strict corpus governance, SHA-256 cryptographic manifests,
and synthetic benchmark generation:

1. Corpus Manifest Schema:
   - Every evaluation dataset is governed by a versioned JSON manifest (`CorpusManifest`);
   - Each entry declares: document relative path, SHA-256 digest, MIME type,
     page count, license type (`synthetic`, `public-licensed`, or `proprietary-governed`),
     provenance source, permitted uses, and slice labels (`language`, `quality`,
     `layout_density`, `vendor_category`);
   - Ground truth annotation files (OCR transcript, extracted JSON, expected verification
     findings, expected verdict) are paired by relative path and SHA-256 digest.

2. Integrity and Provenance Validation:
   - Manifest validation computes and asserts SHA-256 digests of all referenced
     documents and ground truth files before evaluation execution;
   - Missing files, hash mismatches, or missing slice tags immediately abort evaluation;
   - Manifest validator enforces that no real customer PII or unlicensed third-party
     data is referenced by repository fixtures.

3. Repository Benchmark Fixtures:
   - In-tree evaluation fixtures must be 100% synthetic, deterministically generated,
     and license-safe;
   - External proprietary evaluation corpora may be used only outside the Git repository
     by pointing `veridoc-evaluate` to an external manifest path under operator access controls.

## Alternatives considered

- Loading unstructured folders of PDFs without manifest integrity checking.
- Storing unhashed test sets in Git LFS or remote buckets without cryptographic binding.
- Including anonymized real customer invoices directly in source control.

## Consequences

Zero risk of customer data leakage or copyright violations. Tests and benchmark
evaluations are completely deterministic and verify corpus integrity before
running compute-intensive OCR or graph verification.
