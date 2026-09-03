# 0016: Scan uploads before decoding with operator-held quarantine

## Status

Accepted

## Context

Every document endpoint decodes operator- or client-supplied PDFs and
images before OCR. Validation already bounds sizes, signatures, pages,
and pixels, but no control inspects uploads for malicious payloads, and
there is no quarantine, release, or disposal workflow. Phase 10
requires malware scanning with typed failure behavior and an
operator-controlled release/disposal path before document decoding.

## Decision

Phase 10 places a scanning boundary in front of upload decoding on
every document route (`/ocr`, `/extract`, `/process`,
`POST /review/cases`):

- the container runs a signature-based scanner with pinned engine and
  database versions declared in the image;
- each upload is scanned before validation hands it to a decoder; a
  positive or a scanner failure maps to a typed safe error and the
  bytes never reach decoding, OCR, providers, or storage;
- positives move to encrypted quarantine storage with retention and
  operator-only disposal; release back into processing requires an
  explicit operator action recorded with reason, never an automatic
  retry;
- scanner unavailability fails closed: uploads are rejected until the
  operator restores or explicitly bypasses the boundary with a recorded
  reason during an incident.

## Alternatives considered

- Scan after OCR or processing and delete results on a positive.
- Reject positives without quarantine or operator review.
- Fail open when the scanner is unavailable to preserve availability.
- Outsource scanning to an external SaaS verdict service.

## Consequences

Decoders and providers only see scanned bytes, and every quarantine
decision is attributable to the repository owner. The price is latency
per upload and a hard dependency on scanner-database freshness, which
the runbook covers as a maintenance task. Scan-evasion limits are
documented as residual risk for Phase 11.
