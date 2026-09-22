# Operations and Incident Runbook

This runbook defines the operational procedures, deployment profile, secret
rotation, backup/restore drills, incident response, and telemetry monitoring
for the Veridoc Phase 10 deployment profile.

## 1. Architecture and Trust Boundary

Phase 10 targets a single reproducible local Docker container profile
([ADR 0011](decisions/0011-use-local-container-for-phase-10-deployment.md)):
- The container runs as non-root user `veridoc:veridoc` (UID 10001).
- All sensitive data lives on an encrypted single-writer host volume mounted at
  `/data` ([ADR 0015](decisions/0015-encrypted-single-writer-storage.md)).
- Container binds to loopback (`127.0.0.1:8000`).
- TLS terminates at an operator reverse proxy
  ([ADR 0013](decisions/0013-local-identity-with-proxy-tls.md)).
- Secrets are mounted read-only into `/secrets` and injected at startup
  ([ADR 0014](decisions/0014-runtime-secret-injection-and-rotation.md)).

## 2. Image Build and Deployment

### 2.1 Build Container Image

```bash
docker build -t veridoc:latest .
```

The build verifies:
- Pinned `python:3.12.12-slim-bookworm` base image.
- `tesseract-ocr`, `tesseract-ocr-eng`, and `tesseract-ocr-ara` packages.
- Dependencies synchronized strictly from `uv.lock`.

### 2.2 Prepare Host Mount Directories

```bash
# Create encrypted volume directory for databases and quarantine
mkdir -p /opt/veridoc/data/quarantine /opt/veridoc/backups /opt/veridoc/secrets
chown -R 10001:10001 /opt/veridoc/data /opt/veridoc/backups
chmod 700 /opt/veridoc/data /opt/veridoc/backups /opt/veridoc/secrets
```

### 2.3 Populate Secrets

Place credentials into `/opt/veridoc/secrets` with read-only permissions (`chmod 400`):
- `/opt/veridoc/secrets/OPENAI_API_KEY`: Raw API key string.
- `/opt/veridoc/secrets/VERIDOC_ADMIN_TOKEN`: Bearer token (32-256 characters).
- `/opt/veridoc/secrets/actors.json`: Review actor directory with hashed secrets.

```bash
chmod 400 /opt/veridoc/secrets/*
chown -R 10001:10001 /opt/veridoc/secrets
```

### 2.4 Start the Container

```bash
docker run -d \
  --name veridoc \
  --restart unless-stopped \
  -p 127.0.0.1:8000:8000 \
  -v /opt/veridoc/data:/data:rw \
  -v /opt/veridoc/secrets:/secrets:ro \
  -e VERIDOC_REVIEW_ORIGIN="https://veridoc.local" \
  -e VERIDOC_LLM_MODEL="gpt-4o" \
  -e VERIDOC_MAX_CONCURRENCY=16 \
  -e VERIDOC_RATE_LIMIT_CAPACITY=60 \
  -e VERIDOC_RATE_LIMIT_REFILL_PER_SECOND=10 \
  veridoc:latest
```

## 3. Reverse Proxy & TLS Configuration

An operator-managed reverse proxy (Caddy or Nginx) must terminate TLS and
forward traffic to `http://127.0.0.1:8000`.

### 3.1 Caddy Example

```caddy
veridoc.local {
    tls internal
    reverse_proxy 127.0.0.1:8000 {
        header_up Host {host}
        header_up X-Forwarded-For {remote_host}
        header_up X-Forwarded-Proto https
    }
}
```

### 3.2 Nginx Example

```nginx
server {
    listen 443 ssl http2;
    server_name veridoc.local;

    ssl_certificate /etc/ssl/certs/veridoc.local.crt;
    ssl_certificate_key /etc/ssl/private/veridoc.local.key;

    location / {
        proxy_pass http://127.0.0.1:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto https;
    }
}
```

## 4. Secret Management and Rotation

Per [ADR 0014](decisions/0014-runtime-secret-injection-and-rotation.md),
secrets are never stored in images or queried via HTTP.

### 4.1 Rotate OpenAI API Key
1. Update `/opt/veridoc/secrets/OPENAI_API_KEY`.
2. Restart container: `docker restart veridoc`.
3. Verify readiness: `curl -s http://127.0.0.1:8000/ready`.

### 4.2 Rotate Administration Token
1. Update `/opt/veridoc/secrets/VERIDOC_ADMIN_TOKEN`.
2. Restart container: `docker restart veridoc`.
3. Verify administrative access from loopback:
   `curl -H "Authorization: Bearer <new-token>" http://127.0.0.1:8000/admin/reference-data/invoices`.

### 4.3 Rotate Reviewer Password / Session Secret
1. Update actor entry in `/opt/veridoc/secrets/actors.json` with new SHA-256 digest.
2. Restart container: `docker restart veridoc`.
3. Prior sessions remain bounded by 12-hour session lifetime or expire immediately.

## 5. Scheduled Backups and Retention

Per [ADR 0015](decisions/0015-encrypted-single-writer-storage.md), retention keeps
the two most recent verified backups per store plus the live database.

### 5.1 Execute Scheduled Backup

Run inside container or against host volume using `veridoc-backup`:

```bash
docker exec veridoc veridoc-backup \
  --reference-db /data/veridoc-reference.sqlite3 \
  --review-db /data/veridoc-review.sqlite3 \
  --backup-dir /data/backups \
  --quarantine-dir /data/quarantine \
  --keep 2
```

### 5.2 Automate via Host Cron

```cron
0 2 * * * docker exec veridoc veridoc-backup --reference-db /data/veridoc-reference.sqlite3 --review-db /data/veridoc-review.sqlite3 --backup-dir /data/backups --quarantine-dir /data/quarantine --keep 2 >> /var/log/veridoc-backup.log 2>&1
```

## 6. Disaster Recovery: Stopped-Service Atomic Restore

If a database becomes corrupted or requires rollback to a prior verified backup:

1. **Stop the container** to eliminate concurrent writers:
   ```bash
   docker stop veridoc
   ```

2. **Verify live sidecars are absent**:
   Ensure no `-wal`, `-shm`, or `-journal` files exist for the target database.

3. **Restore Reference Database**:
   ```bash
   docker run --rm \
     -v /opt/veridoc/data:/data \
     veridoc:latest \
     veridoc-reference restore \
       --database /data/veridoc-reference.sqlite3 \
       --backup /data/backups/reference-backup-<timestamp>.sqlite3
   ```

4. **Restore Review Database**:
   ```bash
   docker run --rm \
     -v /opt/veridoc/data:/data \
     veridoc:latest \
     veridoc-review restore \
       --database /data/veridoc-review.sqlite3 \
       --backup /data/backups/review-backup-<timestamp>.sqlite3
   ```

5. **Restart Container and Verify Readiness**:
   ```bash
   docker start veridoc
   curl -s http://127.0.0.1:8000/ready
   ```

## 7. Incident Response: Malware Scanning & Quarantine

Per [ADR 0016](decisions/0016-scan-uploads-before-decoding.md):
- All document uploads (`/ocr`, `/extract`, `/process`, `POST /review/cases`)
  are scanned before decoding.
- Malware positives return `422 scan_rejected_positive` and are quarantined.
- Scanner service failure returns `503 scanner_unavailable` (fails closed).

### 7.1 Inspect Quarantined Files

```bash
docker exec veridoc veridoc-quarantine list
docker exec veridoc veridoc-quarantine get <sha256-entry-id>
```

### 7.2 Release False Positive

Release requires a recorded operator reason:
```bash
docker exec veridoc veridoc-quarantine release <sha256-entry-id> \
  --reason "Confirmed legitimate vendor invoice after sandbox detonation."
```

### 7.3 Dispose Malware Payload

Disposal permanently unlinks the quarantined bytes while leaving an audit tombstone:
```bash
docker exec veridoc veridoc-quarantine dispose <sha256-entry-id> \
  --reason "Confirmed malicious payload; unlinked per security policy."
```

## 8. Telemetry and Observability

Per [ADR 0017](decisions/0017-operational-only-telemetry.md):
- Liveness probe: `GET /health` (200 OK).
- Readiness probe: `GET /ready` (200 OK if reference store, review store, identity, OCR engine, and extraction provider are ready; 503 if any dependency is degraded).
- Operational Metrics: `GET /metrics` exports request counts, rate-limit throttles, scan results, and quarantine events.
- Document text, customer names, provider prompts, and secrets are strictly redacted and never recorded in metrics or logs.

## 9. Measured Evaluation Re-run

The Phase 11 decision is `conditional_go` pending slice remediation, and the
Phase 13 corpus (`veridoc-synthetic-benchmark-v2`) satisfies every
preregistered slice minimum. The measured re-run below converts the
remediation corpus into an updated go/no-go decision. It must execute in the
Tesseract-equipped operator environment — never present a fake-harness run
(where OCR and extraction are canned test doubles) as a readiness decision.

Prerequisites:

- Tesseract executable with `eng` and `ara` trained data (`GET /ready`
  reports the OCR engine ready);
- `OPENAI_API_KEY` and `VERIDOC_LLM_MODEL` set to the exact provider
  identity under evaluation;
- a reference database (temporary or a copy — the benchmark never mutates
  operator reference data, but point `--reference-db` at a scratch path to
  be explicit); and
- a clean worktree at the evaluated commit (record the commit hash).

Procedure:

```bash
uv run veridoc-evaluate --manifest tests/fixtures/corpus/manifest.json \
  --reference-db /tmp/eval-reference.sqlite3 \
  --output-json /tmp/eval-report.json \
  --output-markdown /tmp/eval-report.md \
  --evaluation-id eval-remediation-001 \
  --expiry-date 2027-03-16
```

Compare the new report's artifact and provider identity block against the
baseline report's block: any model, serving, region, dependency, language
data, or platform change is drift and forces a fresh re-evaluation instead
of a decision carry-over (ADR 0019). Drift comparison is an operator review
of the two rendered identity blocks; there is no drift subcommand.

Acceptance before recording the decision in
[evaluation-report.md](evaluation-report.md):

- manifest integrity verified (the runner aborts otherwise);
- every slice reports sufficient sample size;
- no threshold was changed for the run (thresholds are preregistered in
  [evaluation-protocol.md](evaluation-protocol.md));
- provider identity matches the evaluated scope, or drift triggers a fresh
  re-evaluation instead (ADR 0019); and
- the report states artifact identity, corpus version, expiry, and residual
  limitations exactly as rendered.

## 10. Auditor Evidence Handoff

Per [ADR 0025](decisions/0025-auditor-evidence-export-for-review-cases.md),
evidence bundles are `confidential`: they carry the full case, including
extracted document content, and prove what the case contained at export
time. Activity after export requires a fresh bundle.

### 10.1 Export a case bundle

Authenticated actors download the bundle from the console case detail
("Export evidence bundle") or call the route directly:

```powershell
curl.exe "$env:VERIDOC_REVIEW_ORIGIN/review/cases/<case_id>/evidence" `
  -H "Origin: $env:VERIDOC_REVIEW_ORIGIN" `
  --cookie "veridoc_review_session=<session-cookie>" `
  -o evidence-<case_id>.json
```

Operators with store access use the maintenance CLI instead (the exporting
identity is recorded on the bundle):

```bash
uv run veridoc-review --database /data/veridoc-review.sqlite3 \
  export --case-id <case_id> --output evidence-<case_id>.json \
  --exported-by operator
```

### 10.2 Verify a bundle on receipt

Verification needs only the bundle file — no store, session, or provider:

```bash
uv run veridoc-review verify-bundle --input evidence-<case_id>.json
```

A non-zero exit means the bundle is not verifiable: reject it and request a
fresh export; never edit a bundle by hand. Store received bundles with
least-privilege access, never on unencrypted backup media, and dispose of
them per operator retention policy once the audit closes.
