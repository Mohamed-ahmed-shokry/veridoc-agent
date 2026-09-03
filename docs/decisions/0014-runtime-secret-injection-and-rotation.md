# 0014: Inject deployment secrets at runtime with operator rotation

## Status

Accepted

## Context

Veridoc reads every credential from the process environment
(`OPENAI_API_KEY`, `VERIDOC_ADMIN_TOKEN`, actor secrets via the actor
file) and already refuses to log, return, or persist raw values. Phase
10 adds a container image and persistent mounts, which creates two new
risks: baking a secret into the image or a manifest, and leaving a
compromised credential valid because no rotation path exists. The
single-operator local profile (ADR 0011) has no vault service.

## Decision

Phase 10 injects all secrets at container start from operator-managed
files outside the image, never from image layers, manifests, logs, or
diagnostic responses:

- `OPENAI_API_KEY` and `VERIDOC_ADMIN_TOKEN` arrive as container
  secrets mounted to memory-only paths and exported into the process
  environment at entrypoint time;
- the review actor file remains an operator-managed file mounted
  read-only into the container at `VERIDOC_REVIEW_ACTORS_FILE`;
- TLS private keys live only on the reverse proxy host, never in the
  container or the repository.

Rotation is an operator procedure owned by the repository owner:
replace the secret file, restart the container, revoke affected
sessions via logout/expiry for actor secrets, and regenerate the admin
token for loopback administration. The runbook records each step with
its revocation check. No in-application rotation endpoint exists in
Phase 10.

## Alternatives considered

- Bake non-production placeholder secrets into the image for
  convenience.
- Add an HTTP credential-rotation endpoint to the application.
- Adopt a vault or cloud secret manager for the local profile.
- Pass secrets as container build arguments.

## Consequences

Images and manifests stay free of `restricted` data (ADR 0012) and one
artifact can run in any operator environment with its own secrets.
Rotation requires a restart and remains manual; automated rotation and
managed secret services belong to a later approved phase.
