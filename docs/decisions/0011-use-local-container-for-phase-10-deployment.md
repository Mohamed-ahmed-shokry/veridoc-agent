# 0011: Use a local container for the Phase 10 deployment profile

## Status

Accepted

## Context

Through Phase 9 Veridoc runs only as a developer-started Uvicorn process
(`uv run uvicorn veridoc.app:app --reload`) with no reproducible runtime
artifact, no resource bounds, no TLS termination, and no deployment
topology. Phase 10 requires exactly one reproducible, security-reviewed
deployment profile for the approved application scope: reference-data
administration, review workflow, SQLite stores, Tesseract OCR, and the
OpenAI Responses adapters. The profile must demonstrate identity,
transport, secret, storage, recovery, and privacy controls without
claiming production readiness, which remains a Phase 11 decision.

The repository owner holds all four Phase 10 operational roles:
vulnerability response, credential rotation, backup drills, and incident
handling.

## Decision

Phase 10 targets a single local Docker container image as the only
supported runtime artifact:

- pinned minimal Python 3.12 base image with an immutable digest;
- non-root runtime user;
- explicit Tesseract executable plus declared language data baked into
  the image;
- read-only application filesystem where practical, with a single
  writable mount for the two SQLite stores, temporary upload files, and
  backups;
- declared CPU, memory, and temporary-storage limits;
- SQLite retained for both reference and review stores on the mounted
  data directory (encryption and single-writer profile in ADR 0015);
- network edge limited to host-local loopback by default, with an
  operator-controlled reverse proxy providing TLS termination when
  browser access to `/review/console` is needed (TLS profile in
  ADR 0013).

The trust boundary encloses the container image, the mounted data
directory, the operator host, and the configured OpenAI provider
endpoint. Everything outside it — client browsers, the host network
beyond loopback, backup media — is untrusted. No second target is
supported in Phase 10.

## Alternatives considered

- Run Uvicorn as a host-managed service without a container runtime.
- Target a cloud VM or managed container host as the Phase 10 profile.
- Support multiple deployment targets in Phase 10.
- Replace SQLite with a remote database for the deployment profile.

## Consequences

All later Phase 10 work (health signals, identity, secrets, storage,
scanning, observability, runbooks) builds against one reproducible
artifact instead of developer workstations. The image is deterministic
from reviewed source and immutable dependencies, so the Phase 11
evaluation can pin an exact artifact identity. Multi-target support,
multi-region availability, remote databases, and any production go-live
claim remain out of scope until separately approved.
