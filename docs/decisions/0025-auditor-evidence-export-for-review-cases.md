# 0025: Export digest-bound auditor evidence bundles for review cases

## Status

Accepted

## Context

Phase 9 stores each review case as an immutable, schema-versioned,
digest-verified processing snapshot plus an append-only ordered event
history (ADR 0009). That record is only visible through the authenticated
API and browser console: no artifact exists that an auditor can take away,
store under their own controls, and verify independently of the review
database. Potential approaches — screenshots, database copies, ad-hoc JSON
dumps of API responses — are either unverifiable after the fact or leak
unbounded store internals.

## Decision

Phase 15 adds a first-class evidence bundle per case with offline
verification semantics:

- A bundle binds one canonical case rendering: case identifiers, status,
  version, actor attribution, timestamps, the complete `ReviewSnapshot`
  (including its content digest), and the full ordered `ReviewEvent`
  history, plus bundle metadata (bundle format version, export timestamp,
  exporter identity).
- A canonical bundle digest (SHA-256 over canonical JSON) makes the bundle
  tamper-evident: any edit to the snapshot, any dropped, reordered, or
  edited event, or any digest change fails verification.
- Verification is offline and store-independent: given only the bundle
  bytes, the verifier re-parses the schema, recomputes the snapshot digest
  against its embedded result, checks event-chain continuity (versions
  start at the creation event and increment by exactly one with matching
  case identifiers), and recomputes the bundle digest. No database, session,
  or provider access is required.
- Bundles carry the case as-is, including extracted document content. They
  are `confidential` per ADR 0012: auditor handling rules (least-privilege
  storage, no unencrypted backup media, retention per operator policy)
  apply, and the runbook documents the handoff. No redaction or PDF
  rendering is attempted; both would weaken verifiability.
- Delivery reuses existing trust boundaries unchanged: the export route
  requires the same actor authentication as case detail, and the
  `veridoc-review` CLI operates on the same dedicated review store.
  Verification never mutates a case, an event, or the store.

## Alternatives considered

- Screenshots or saved console pages as audit evidence.
- Raw SQLite backup files handed to auditors.
- Ad-hoc API response dumps with no digest or chain checks.
- Redacted or PDF-rendered auditor reports generated server-side.

## Consequences

Auditors receive a self-verifying artifact whose checks run anywhere,
while case immutability and the append-only event log stay untouched:
export and verification are read-only over canonical detail. Bundles do
not replace backups (which remain the recovery mechanism) and do not
authorize disclosure on their own — the exporting actor's authority and
the auditor's handling obligations are operator policy, recorded in the
runbook. A bundle proves what the case contained at export time; activity
after export requires a fresh bundle.
