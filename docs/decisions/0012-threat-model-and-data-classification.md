# 0012: Adopt a threat model and data classification for Phase 10

## Status

Accepted

## Context

Phase 10 places the Veridoc application in a container with a network
edge, persistent stores, and operator tooling for the first time. The
codebase already enforces bounded uploads, grounded verification,
constant-time credential comparison, auth-before-storage ordering, and
metadata-only logging, but no document states what attackers, assets,
and data classes the deployment profile defends against. Without that
record, later Phase 10 controls (identity, secrets, storage, scanning,
observability) have no shared scope to satisfy.

## Decision

Phase 10 adopts this threat model for the local container profile in
ADR 0011:

- Attackers: network-adjacent clients probing unauthenticated document
  routes; malicious or malformed uploads targeting decoders, OCR, and
  provider payloads; credential-guessing against administration and
  review session endpoints; a compromised backup medium or stolen data
  directory.
- Explicitly out of scope: nation-state supply-chain compromise of the
  base image beyond digest pinning and image scanning; OpenAI-side data
  handling beyond residency controls and storage-disabled requests;
  endpoint-device compromise of the operator host.
- Assets: uploaded documents, OCR text, extraction results, reference
  facts, review cases and events, session records, backups, credentials,
  logs, metrics, and traces.

Data classification:

- `restricted`: actor credentials, session/CSRF tokens, admin token,
  OpenAI key, raw uploaded bytes, OCR text, extracted PII-bearing
  fields — never logged, never in responses except the typed result of
  the requesting call, never in images or manifests.
- `confidential`: reference facts, review snapshots/events, backups —
  encrypted at rest, least-privilege access, covered by retention and
  disposal controls.
- `operational`: correlation IDs, route templates, status codes,
  durations, aggregate resource metrics — the only telemetry permitted.

Every later Phase 10 control must trace to one attacker, asset, or data
class above; anything else needs a new ADR.

## Alternatives considered

- Defer the threat model until after container packaging exists.
- Adopt a generic STRIDE-per-endpoint catalog instead of one profile
  model.
- Classify all persisted data as a single sensitivity tier.

## Consequences

Identity, secret, storage, quarantine, and observability work share one
reviewable scope, and Phase 11 can check each acceptance threshold
against it. Threats outside the model (host compromise, provider-side
handling) are documented limitations rather than silent gaps.
