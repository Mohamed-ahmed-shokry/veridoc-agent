# 0019: Capture frozen provider and artifact identity with drift detection triggers

## Status

Accepted

## Context

Veridoc uses external vision LLMs (OpenAI Responses API) for structured invoice
extraction and optional explanation guidance, alongside local Tesseract OCR
language data and SQLite schema migrations. Hosted model providers frequently
update backend serving infrastructure, model weights, or rate behaviors without
changing the public model alias (e.g. `gpt-4o-mini`). Furthermore, local library
or language asset updates can alter OCR tokenization and verification behavior.
An evaluation result is valid only for the exact artifact and provider identity
under which it was measured.

## Decision

Phase 11 implements comprehensive artifact and provider identity capture with
explicit drift invalidation triggers:

1. Artifact Identity Fingerprint:
   - Application version and Git commit SHA;
   - Python runtime version and platform;
   - SHA-256 digest of locked dependencies (`uv.lock`);
   - Tesseract executable version and SHA-256 digests of all configured
     `<lang>.traineddata` assets in `TESSDATA_PREFIX`;
   - Current schema migration version for both reference and review SQLite stores.

2. Provider Identity Fingerprint:
   - Configured model identifier (`VERIDOC_LLM_MODEL`);
   - Hash of system prompt and JSON schema definitions sent to the provider;
   - Configured extraction temperature and timeout bounds;
   - Observed provider response headers (e.g. `system_fingerprint`, model version
     stamp) when available from the Responses API.

3. Drift Triggers and Invalidation:
   - Any modification in artifact identity (code commit, dependency change,
     trained data modification, database migration) marks previous evaluation
     records as stale;
   - Any detected change in provider system fingerprint or model configuration
     triggers a re-evaluation requirement before decisions remain valid;
   - Because hosted provider backends cannot be completely frozen by client code,
     the evaluation report must explicitly declare hosted provider opacity as a
     reproducibility limitation and cannot grant an indefinite approval.

## Alternatives considered

- Relying solely on the high-level model string (e.g. `VERIDOC_LLM_MODEL`).
- Ignoring local OCR traineddata file hashes.
- Treating evaluation results as evergreen across application releases.

## Consequences

Every evaluation run is pinned to a machine-readable provenance record.
Upgrading dependencies or language assets immediately indicates that re-evaluation
is required.
