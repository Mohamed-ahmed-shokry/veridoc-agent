# 0015: Keep SQLite on encrypted single-writer storage with drilled recovery

## Status

Accepted

## Context

Veridoc persists reference facts and review cases in two independent
SQLite databases with forward-only migrations, validated backup, and
stopped-service atomic restore (ADRs 0007, 0009, 0010). Phase 10 must
place both stores on a deployment storage profile with encryption,
least-privilege access, retention, scheduled backups, and verified
restore drills — without changing persistence technology, which would
need a separate stack-change approval.

## Decision

Phase 10 keeps SQLite for both stores on a single-writer encrypted
volume mounted into the container at one data directory:

- the host volume is encrypted at rest with an operator-managed key;
- exactly one container process writes each database; concurrent
  writers are a configuration error, not a supported topology;
- database credentials are filesystem permissions (least privilege:
  container user read/write, no other access);
- scheduled encrypted backups use the existing `veridoc-reference` and
  `veridoc-review` online-backup commands to operator-managed backup
  media outside the container;
- restore follows the existing stopped-service atomic procedure, and
  the repository owner performs a documented restore drill before the
  Phase 10 gate closes, recording the observed recovery result;
- retention keeps the two most recent verified backups per store plus
  the current live database; older media is disposed by operator
  deletion.

## Alternatives considered

- Replace SQLite with a remote database for the deployment profile.
- Run multiple container writers against one database file.
- Store backups inside the container image or data volume.
- Keep backups unencrypted because the profile is local.

## Consequences

Persistence code and migration ledgers stay unchanged, so all existing
repository, migration, and backup/restore tests keep covering the
deployment stores. Encryption and recovery rest on host controls plus
operator drills rather than application cryptography; key loss destroys
the stores, which the runbook states explicitly. A remote database or
multi-writer topology needs its own approval and ADR.
