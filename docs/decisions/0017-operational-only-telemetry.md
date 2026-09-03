# 0017: Export operational-only telemetry with redaction tests

## Status

Accepted

## Context

The application already logs metadata-only request records (request
ID, method, static route template, status, duration) and sends only
canonical findings to the explanation provider with storage disabled.
Phase 10 adds container metrics, traces, and structured log export for
the first time, which creates new paths for `restricted` data (ADR
0012) to leak into telemetry, crash dumps, or support artifacts.

## Decision

Phase 10 exports only `operational`-class telemetry: request IDs,
static route templates, status codes, durations, aggregate CPU/memory/
temporary-storage figures, and scanner/quota counters. Collection
excludes document bodies, OCR text, extracted values, findings prose,
credentials, session tokens, temporary paths, and provider payloads;
unknown paths keep the `<unmatched>` marker instead of raw values.

Every telemetry sink — logs, metrics, traces, crash reports, and
support bundles — is covered by redaction tests asserting that a
`restricted` fixture value appears in none of them. Provider and data
residency is documented: extraction/explanation calls carry no stored
state (storage disabled), and the runbook records the configured
provider region as informational. Telemetry lives on the operator host
with the same least-privilege access as the data directory.

## Alternatives considered

- Export full request/response payloads for debugging convenience.
- Log raw unknown paths to ease route diagnosis.
- Leave provider region and storage settings undocumented.
- Cover only logs with redaction tests, not metrics/traces/dumps.

## Consequences

Operators get latency, error-budget, and resource signals without a
second sensitive data store to protect. Debugging power is reduced by
design: incident diagnosis uses correlation IDs plus typed error codes,
never payload capture. Any future telemetry field above `operational`
needs a new ADR and its own redaction test.
