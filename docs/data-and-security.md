# Data and Security

Veridoc processes commercially sensitive documents at an untrusted boundary.
Phase 8 accepts document bytes for one ephemeral OCR, extraction, or complete
processing request. Complete processing reads local reference facts from an
explicitly configured SQLite path, but never writes them or persists the current
upload. Authenticated reference-data administration owns fact writes.
When `/extract` or `/process` is used, the extraction adapter sends the current
request's OCR text and normalized page images to the configured OpenAI provider.
The internal explanation adapter sends only canonical verification findings,
never document bytes, page images, or raw OCR text. The local `/review` page
submits the selected document to `/process` without retaining it in the page.
Authenticated `/admin/reference-data/*` routes can manage approved local
reference facts; they never accept document uploads. The Phase 9 `/review/*`
routes require a session-authenticated actor and run the same processing
pipeline, then persist its result as an immutable, digest-verified case
snapshot in a dedicated local SQLite store, separate from reference data.
This is still a local development service and must not receive real invoices
or production data.

## Allowed development data

Commit only:

- synthetic invoices and purchase orders;
- fictional vendor histories;
- deterministic programmatically generated fixtures; or
- appropriately licensed subsets of public datasets such as SROIE or CORD.

For a public subset, record its source, license, selected files, and any required
attribution beside the fixture-generation instructions. Do not assume that a
publicly downloadable document is licensed for redistribution.

Phase 2 tests use generated fictional invoice bytes from
`tests/fixtures/fictional_invoice.py`; no source document is checked in.
Phase 3 SQLite and verification tests construct fictional vendor history in
memory or in temporary test databases only.
Phase 4 explanation tests construct typed fictional findings in memory and mock
the provider boundary. Phase 5 processing and review tests use the same
synthetic boundaries; Phase 6 integration tests use a temporary database and
fake OCR/extraction boundaries. No browser upload or reference database is
committed.
Phase 8 administration, migration, import, backup, and restore tests use
fictional records and pytest temporary databases only.
Phase 9 review tests use fictional actor secrets (never real credentials),
synthetic uploaded documents, and pytest temporary review databases only; no
review database or actor file is committed.

## Prohibited data

Never commit or paste into issues, tests, snapshots, logs, or documentation:

- real invoices or purchase orders;
- production documents or database exports;
- personal or customer information;
- real vendor bank, tax, or contact details;
- credentials, API keys, session tokens, or connection strings; or
- confidential business data.

If prohibited data is discovered, stop work, avoid copying it further, and tell
the user which tracked or untracked path is affected. Do not publish or rewrite
history without explicit direction.

## Fixture generation

Fixture generators must produce fictional data from fixed inputs. Keep fixtures
small and tailored to one scenario. The fixture generator is deterministic
and contains only fictional vendor, invoice, purchase-order, and total text.

Generation must not call production services or sample local documents. A
fixture change belongs with its focused test or in a separate reviewable fixture
commit when substantial. Generated fixtures should include assertions for
determinism and expected behavior so accidental drift is visible.

## Secrets and environment files

The repository tracks `.env.example` with safe comments only. `.gitignore`
excludes `.env` and `.env.*` while explicitly allowing `.env.example`.

The application reads optional `TESSERACT_CMD`, `TESSERACT_LANG`, and the
bounded `TESSERACT_TIMEOUT_SECONDS`, plus the `OPENAI_API_KEY` and
`VERIDOC_LLM_MODEL` used by `/extract` and `/process`, and the optional
`VERIDOC_REFERENCE_DATABASE` path used by processing and administration, from
the process environment. `VERIDOC_ADMIN_TOKEN` is required for administration
and must be a randomly generated 32-256 character value. The review workflow
additionally reads `VERIDOC_REVIEW_ACTORS_FILE` (path to the operator-managed
actor file — never commit it), `VERIDOC_REVIEW_ORIGIN` (the exact HTTPS
browser origin allowed to authenticate), and the optional
`VERIDOC_REVIEW_DATABASE` path (must differ from the reference database). The
application does not load `.env` files. Keep credentials, actor files, and
deployment paths out of committed files, and use unmistakably fake
placeholders in `.env.example` when examples are needed.

Send the administration token only in the `Authorization: Bearer` header, and
a review actor's credential the same way, only to `POST /review/session`.
Never put a credential, token, or actor secret in a URL, query value, request
body, source file, shell history, or log. Missing configuration returns a
safe `503`; missing or invalid request credentials return the same generic
`401` challenge in both cases. Administration hashes the configured and
presented tokens to fixed-length SHA-256 digests before a constant-time
comparison, but the shared token provides neither individual identity nor
role-based authorization; the review workflow's per-actor digest comparison
does provide both.

Before committing, inspect staged changes for accidental credentials and verify
that any local `.env` remains ignored.

## Safe logging

Every response carries an `X-Request-ID` correlation value. A caller-supplied
value is accepted only when it is 1 to 128 safe letters, digits, periods,
underscores, or hyphens; otherwise the service generates one. Do not include
document identifiers, customer data, credentials, or secrets in that header.

The `veridoc.request` logger writes one metadata-only completion record with the
request ID, method, static route template, status code, and duration. Unmatched
requests use a coarse `<unmatched>` marker, so neither concrete path parameters
nor raw unknown paths enter the log. It does not log complete documents, raw OCR
text, rendered pages, extracted names or identifiers, line items, credentials,
authorization headers, query values, raw Tesseract output, provider responses,
local temporary paths, persisted reference facts, verification findings,
explanation narratives, or numerical context.
Request-validation failures return a generic `invalid_request` response and do
not echo submitted field names or values.

## Upload validation

`/ocr`, `/extract`, and `/process` implement the following controls before
decoding, OCR, or external-provider input:

1. reject a complete multipart body over the 10 MiB file limit plus 64 KiB of
   framing before parsing, including under ASGI mounts or root paths, then read
   the file in bounded chunks;
2. allow only PDF, PNG, and JPEG signatures;
3. compare a supplied `Content-Type` with the detected signature;
4. sanitize client filenames for display and never use them as paths;
5. reject malformed PDFs at open or page inspection, plus empty, encrypted, or
   repaired PDFs;
6. bound PDFs to 20 pages, each decoded/rendered page to 20,000,000 pixels, and
   all rendered PDF pages to 50,000,000 pixels in aggregate;
7. bound normalized PNG page images to 32 MiB in aggregate during encoding,
   before an oversized result is retained or sent to a provider; and
8. return safe structured errors without internal paths or stack traces.

Filename extensions and `Content-Type` alone are not trusted. Validation and
upload closure complete before OCR, provider, processing, or repository
dependency construction. Rasterization and OCR run outside the async request
loop and each Tesseract page retains its configured timeout. Extraction and
explanation provider calls have a fixed 120-second application deadline, and
their request-scoped clients close during dependency teardown.

## Temporary files and retention

Validated upload bytes are written to a private OS temporary directory with a
server-generated filename for the processing lifetime. The file and directory
are removed on success, validation failure, OCR failure, cancellation, and
unexpected exceptions through the context-managed storage boundary.

The OCR, extraction, and complete-processing paths retain no uploaded document,
rendered page, OCR artifact, or processing result. Rendered page images exist
only in memory while the current extraction call is built. The extraction and
explanation Responses adapters set `store=False`. The explanation adapter
receives canonical verification findings only, and the service retains their
deterministic numerical context rather than a provider calculation. That request
option and narrowed data payload do not replace an organization-specific review
of provider retention, regional-processing, account, and contractual controls.

OCR engine and structured provider output remain untrusted. The OCR boundary
rejects malformed page results and drops non-finite or out-of-range confidence
values. Amounts and quantities are bounded before arithmetic, evidence pages
must exist in the current OCR result, and any supplied OCR text span must match
its referenced page after normalization. Invalid provider output maps to a safe
extraction-processing error and is never passed to verification. Malformed
explanation drafts use deterministic guidance rather than causing processing to
fail.

## Reference-data administration boundary

Administration accepts typed invoice and purchase-order facts, not document
bytes, OCR text, provider responses, or verdicts. Each created record stores a
server-generated identifier, client-declared source and external identifier,
creation time, update time, and optional `retention_until` date. Source and
external identifier remain immutable on update so later facts retain their
declared provenance. These fields are metadata, not proof that a source is
trustworthy; operators must admit only approved reference facts.

The boundary limits create/update JSON request bodies and raw JSON import files
to 1 MiB before parsing. Each invoice or purchase order is limited to 200 line
items, and each import contains at most 500 total records. Imports apply one
explicit `reject`, `skip`, or `replace` conflict policy inside one transaction.
Invalid input or a rejected conflict rolls back the entire write, and dry runs
always roll back.

The SQLite adapter applies the same canonical vendor-key and bounded record
schema to verification-facing repository writes, so internal callers cannot
bypass the persisted-data contract used by administration. It also treats rows
read from SQLite as untrusted: facts and metadata are revalidated, silent
normalization is rejected, and malformed stored values map to the safe
reference-data availability error.

Migration 4 enforces one row per `(parent_id, position)` in both line-item
tables. This prevents ambiguous child ordering and supplies the index used by
ordered parent hydration; schema validation rejects a current ledger if either
index is missing or has a different shape.

Purchase-order natural-key conflicts are scoped to vendor key plus purchase
order number. Parameterized repository queries protect SQL boundaries; this
does not make unreviewed input trustworthy. Public errors identify the safe
error category without exposing database paths, SQL text, credentials, or raw
reference payloads.

## Local reference-data retention

`SQLiteInvoiceRepository` persists invoice and purchase-order reference fields
only at `VERIDOC_REFERENCE_DATABASE` (or the local default
`veridoc-reference.sqlite3`) when processing or administration is configured.
It does not persist
document bytes, OCR text, page images, evidence spans, credentials, provider
responses, explanations, or final verdicts. Never seed it with real data in this
local Phase 8 stage. The project ignores `*.db`, `*.sqlite`, and `*.sqlite3` as
defense against accidental commits; ignore rules do not encrypt data, set
retention periods, control backups, or authorize storage.

Phase 8 routes create, read, update, delete, and import reference records behind
the shared local token. A `retention_until` value records an operator-supplied
policy date but does not automatically delete or archive data. Operators remain
responsible for authorized lifecycle decisions.

The `veridoc-reference backup` command uses SQLite's online backup API without
modifying the source. It checks database and foreign-key integrity, then applies
supported migrations and validates the complete migration history plus required
table, column, declared-type, key, constraint, and index invariants on a
disposable copy before that copy's migration transaction commits. It also
rejects triggers on managed tables and hydrates every fact, metadata field, and
attached line item through the bounded persistence models. The command atomically
publishes the original snapshot only after those checks, preserving the source
schema version.
Backup destinations and both restore inputs and destinations must have no live
WAL, SHM, or rollback-journal sidecar. Neither operation may use an output path
that names a sidecar of its own source, even if that sidecar does not currently
exist. Restore additionally requires a stopped service, explicit
`--confirm-replace`, and a valid source backup. It validates the same database
structure and persisted-row semantics on a temporary sibling copy before
atomically replacing the configured database, so a failed restore leaves the
existing database unchanged. Store backups outside the repository with the same
confidentiality, access, retention, encryption, and disposal controls as the
database. The command supplies a mechanism, not a backup policy or recovery
guarantee.

## Phase 9 review workflow security

### Actor secrets and sessions

Review actors are defined in an operator-managed JSON file outside the
repository at `VERIDOC_REVIEW_ACTORS_FILE`, containing only actor IDs, roles,
and fixed-length SHA-256 secret digests — never a raw credential. Never
commit that file. `authenticate_actor` scans every configured actor's digest
with `secrets.compare_digest` and does not short-circuit on the first match,
so response timing does not reveal which actor (if any) a presented
credential belongs to; missing, malformed, and incorrect credentials all
return the same generic `401 invalid_review_credentials`.

A successful login exchanges the credential for a random opaque session
token; only its SHA-256 digest, actor ID, creation time, expiry, and
revocation time are ever persisted, in the dedicated review database, never
in the reference-data database or a log. The session cookie is `HttpOnly`,
`Secure`, `SameSite=Strict`, scoped to `Path=/review`, and fixed to a
12-hour expiry; logout revokes the server-side record so a stolen cookie
stops working immediately, not just when it expires. No credential or
session token may reach `localStorage`, `sessionStorage`, a URL, rendered
HTML, a log line, or an error body — the console page reads the CSRF cookie
via `document.cookie` (it is not `HttpOnly` by design, per the double-submit
pattern) but never reads or displays the session cookie itself.

### CSRF and origin

Every state-changing review request must present an `X-CSRF-Token` header
that exactly matches the non-`HttpOnly` `veridoc_review_csrf` cookie
(compared with `secrets.compare_digest`), and its `Origin` header must
exactly equal the configured `VERIDOC_REVIEW_ORIGIN` (an `https://` origin
with no path or query). Both checks run before any repository or processing
dependency resolves, including the untrusted document upload path — a
rejected actor or forged request never reaches OCR, extraction, the
reference database, or a review-store write. `POST /review/session` itself
is exempt from the CSRF-token check (no session exists yet to have issued
one) but still requires the exact `Origin` match. The review workflow is
unavailable — every route returns `503 review_authentication_unavailable` —
unless `VERIDOC_REVIEW_ORIGIN` is configured as an HTTPS origin, so the
`Secure` session cookie is never expected to travel over plain HTTP.

### Review data and idempotency

`Idempotency-Key` is required on every mutating review request. A replayed
key with the exact same request body returns the original result; a reused
key with a different body returns `409 review_idempotency_conflict` rather
than silently applying the new request or silently keeping the old one. A
concurrent writer that loses an optimistic-version race
(`expected_version` mismatch) never partially applies its write: the
repository detects the loss via `UPDATE ... WHERE version = ?` returning zero
rows, before any event is appended.

The review store never persists a raw document, rendered page, OCR
artifact, or provider response — only the same typed `ProcessingResult` a
processing response already returns, stored once and never mutated. Every
subsequent change is a new immutable event, not an edit; nothing in the
review workflow can retroactively alter what a snapshot says a document's
extraction, findings, or verdict were. The `review_cases` table reserves a
`retention_until` column for future operator policy, but Phase 9 exposes no
route to set it and performs no automated retention or purge; there is also
no case-deletion route (ADR 0010). Treat the review database with the same
confidentiality as the reference database — never seed it with real invoice
or purchase-order data.

### Review backup and recovery

`veridoc-review backup` and `veridoc-review restore` mirror the
`veridoc-reference` maintenance command's guarantees independently (ADR
0009): online backup without modifying the source, full schema and
persisted-row validation on a disposable copy before the migration
transaction commits, and atomic publication only after every check
succeeds. Both commands refuse a source or destination with a live WAL,
SHM, or rollback-journal sidecar, and neither may write to a path that
names its own source's sidecar. Restore additionally requires a stopped
service and a valid source backup, and validates database and foreign-key
integrity again on a temporary sibling before atomically replacing the
destination — a failed restore leaves the existing review database
unchanged. Because each case carries its own frozen, digest-verified
snapshot, restoring a review backup never requires recovering the
historical reference database that was live when a restored case was
created; processing performed after a restore uses whichever reference
database is currently configured, which may differ from what was in effect
originally. Store review backups with the same confidentiality, access,
retention, encryption, and disposal controls as the review database itself.

## Current security limitations

Phase 8 authenticates local reference-data administration with one shared
Bearer token; Phase 9 authenticates the review workflow per actor with
session cookies, CSRF protection, and two roles (`reviewer`,
`review_admin`). Neither has token rotation/revocation service, TLS
termination, rate limiting, malware scanning, encrypted storage, a secret
manager, a durable compliance-grade audit log, a privacy workflow, provider
data-residency controls, database access control, or a managed backup
policy. The local actor file has no self-registration, password reset, or
remote directory integration and is an operator-managed local control, not a
production identity system. `POST /ocr`, `POST /extract`, `POST /process`,
and the older `GET /review` demo page remain unauthenticated. The request ID
and record/event timestamps are operational metadata, not a compliance-grade
audit trail. Tesseract availability, model selection, provider account
controls, and trained-data selection are deployment responsibilities. The
service is not production ready, enterprise grade, fraud proof, or safe for
real documents.
