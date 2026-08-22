# 0008: Use a local actor file and HttpOnly sessions for Phase 9 review

## Status

Accepted

## Context

Phase 9 adds an accountable human-review workflow around an immutable
`ProcessingResult`. Reviewers must be individually attributable, and the
browser UI needs a session rather than a raw credential on every request. The
existing `VERIDOC_ADMIN_TOKEN` bearer token (ADR 0006) is a single shared
secret with no per-actor identity or role and must not authenticate review
routes. Adding a full identity provider, self-registration, or SSO would
exceed the approved local, synthetic-data-only phase.

## Decision

Define stable local actor identifiers behind a typed `ReviewAuthenticator`
boundary with two roles only: `reviewer` (read cases, claim an unassigned
case, act on a case assigned to that actor) and `review_admin` (read all
cases, assign or reassign cases, and perform every reviewer action).

The initial local adapter reads an operator-managed actor file outside the
repository containing actor IDs, roles, and fixed-length secret digests. Raw
credentials must never be committed, stored in the review database, logged,
or returned. Compare presented credentials to stored digests with
`secrets.compare_digest`, matching the constant-time pattern already used for
administration (ADR 0006).

For the browser UI, exchange the actor credential for a random server-side
session identifier. Store only its digest, actor ID, creation time, expiry,
and revocation time. Send the opaque session in an `HttpOnly`, `Secure`,
`SameSite=Strict` cookie, and require a separate CSRF token plus exact
configured-origin validation on every state-changing browser request. Session
expiry and logout must invalidate the server record. No credential or session
token may enter `localStorage`, `sessionStorage`, a URL, rendered HTML, logs,
or error bodies. The authenticated review UI is unavailable unless an HTTPS
review origin is configured.

Dependency ordering must authenticate and authorize a request before
resolving the review repository or processing service, matching the
auth-before-storage pattern already used for administration.

## Alternatives considered

- Reuse `VERIDOC_ADMIN_TOKEN` for review routes.
- Store raw actor passwords in the review SQLite database.
- Send the session token in a query parameter or non-`HttpOnly` cookie.
- Add a third role, or per-case granular permissions, in Phase 9.
- Integrate an external identity provider or SSO in Phase 9.

## Consequences

Reviewers gain individual attribution and role-scoped authorization without a
new runtime dependency. The local actor file is an operator-managed local
control, not a production identity system: it has no self-registration,
password reset, or remote directory integration. Phase 10 may replace the
local authenticator and TLS profile for remote deployment but must preserve
stable actor attribution and the session-secrecy properties defined here.
