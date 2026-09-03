# 0013: Keep local actor identity with proxy-terminated TLS for Phase 10

## Status

Accepted

## Context

Phase 8 authenticates reference-data administration with one shared
bearer token and Phase 9 authenticates review work with per-actor
secrets exchanged for `HttpOnly`/`Secure` sessions plus CSRF and exact
origin checks. Phase 10 exposes the application through a container
network edge for the first time. The roadmap requires migrating the
review actor/session model to the deployment identity and replacing or
disabling the shared administration token for remote access, plus an
approved TLS profile. The deployment is a single-operator local profile
(ADR 0011), so a production identity provider would add remote
infrastructure without a second operator to justify it.

## Decision

Phase 10 keeps the Phase 9 local actor file, roles, session, CSRF, and
exact-origin model unchanged as the deployment identity: stable actor
IDs preserve attribution across the container boundary with no mapping
layer. The Phase 8 shared administration token remains valid only for
loopback-local administration; when the container is served beyond
loopback, administration routes refuse with the safe unavailable
response instead of accepting the shared token as a remote credential.

TLS terminates at the operator-controlled reverse proxy, never in the
container: the container serves plain HTTP bound to loopback, and the
proxy presents the configured `VERIDOC_REVIEW_ORIGIN` HTTPS origin.
`Secure` session cookies therefore travel only over the proxy's TLS
segment, and the application's existing exact-origin check continues to
reject anything but the configured origin. Certificate issuance and
renewal for the local origin are operator responsibilities recorded in
the Phase 10 runbook, not application behavior.

## Alternatives considered

- Introduce an external identity provider (SSO/OIDC) for the review
  workflow in Phase 10.
- Terminate TLS inside the container with a baked-in certificate.
- Keep accepting the shared administration token on remote routes.
- Map review actors to proxy-authenticated identities.

## Consequences

Actor attribution stays stable across the deployment boundary and no
parallel production credential survives: remote callers cannot use the
shared token. The cost is explicit: single-operator local identity only,
no SSO, no multi-user directory, and proxy TLS misconfiguration fails
closed (sessions and admin routes unavailable) rather than open. A
multi-operator or hosted identity remains a separately approved phase.
