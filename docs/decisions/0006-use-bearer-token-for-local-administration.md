# 0006: Use a bearer token for local administration

## Status

Accepted

## Context

Phase 8 adds mutation and import operations for local invoice and purchase-order
reference facts. These operations must not be available through the public
processing boundary, and the existing application has no user, session, or role
model. Adding a full identity system would exceed the approved local phase.

## Decision

Protect every `/admin/reference-data` route with one dedicated bearer token from
the `VERIDOC_ADMIN_TOKEN` process environment variable. The configured token
must contain at least 32 characters. Hash the configured and presented tokens to
fixed-length SHA-256 digests, compare those digests with
`secrets.compare_digest`, and return the same generic `401` response for
missing, malformed, or incorrect credentials. Return a safe `503` response when
the server has no valid administrative token configured.

The token must never appear in URLs, logs, exception messages, committed files,
or response bodies. Rotation replaces the environment value and restarts the
local service. Request logs continue to contain only correlation and HTTP
metadata.

## Alternatives considered

- Put an administrative secret in a query parameter.
- Reuse an OpenAI provider credential.
- Add HTTP Basic credentials with a stored password.
- Introduce users, sessions, roles, or an external identity provider in Phase 8.

## Consequences

Phase 8 gains a small auditable authorization boundary with no new dependency.
The shared token provides no individual attribution, roles, revocation list, or
browser session. It is suitable only for the documented local administration
boundary and does not make Veridoc production-ready. Phase 9 or Phase 10 must
select a real actor and authorization model before persistent human workflows or
remote deployment.
