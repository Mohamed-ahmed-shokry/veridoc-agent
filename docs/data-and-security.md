# Data and Security

Veridoc processes commercially sensitive documents at an untrusted boundary.
Phase 8 accepts document bytes for one ephemeral OCR, extraction, or complete
processing request. Complete processing reads and writes local reference facts
at an explicitly configured SQLite path, but never persists the current upload.
When `/extract` or `/process` is used, the extraction adapter sends the current
request's OCR text and normalized page images to the configured OpenAI provider.
The internal explanation adapter sends only canonical verification findings,
never document bytes, page images, or raw OCR text. The local `/review` page
submits the selected document to `/process` without retaining it in the page.
Authenticated `/admin/reference-data/*` routes can manage approved local
reference facts; they never accept document uploads. This is still a local
development service and must not receive real invoices or production data.

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

The application reads optional `TESSERACT_CMD` and `TESSERACT_LANG`, plus the
`OPENAI_API_KEY` and `VERIDOC_LLM_MODEL` used by `/extract` and `/process`, and
the optional `VERIDOC_REFERENCE_DATABASE` path used by processing and
administration, from the process environment. `VERIDOC_ADMIN_TOKEN` is required
for administration and must be a randomly generated 32-256 character value.
The application does not load `.env` files. Keep credentials and deployment
paths out of committed files, and use unmistakably fake placeholders in
`.env.example` when examples are needed.

Send the administration token only in the `Authorization: Bearer` header. Never
put it in a URL, query value, request body, source file, shell history, or log.
Missing configuration returns a safe `503`; missing or invalid request
credentials return the same generic `401` challenge. The application hashes the
configured and presented tokens to fixed-length SHA-256 digests before a
constant-time comparison, but the shared token provides neither individual
identity nor role-based authorization.

Before committing, inspect staged changes for accidental credentials and verify
that any local `.env` remains ignored.

## Safe logging

Every response carries an `X-Request-ID` correlation value. A caller-supplied
value is accepted only when it is 1 to 128 safe letters, digits, periods,
underscores, or hyphens; otherwise the service generates one. Do not include
document identifiers, customer data, credentials, or secrets in that header.

The `veridoc.request` logger writes one metadata-only completion record with the
request ID, method, path without query text, status code, and duration. It does
not log complete documents, raw OCR text, rendered pages, extracted names or
identifiers, line items, credentials, authorization headers, query values, raw
Tesseract output, provider responses, local temporary paths, persisted reference
facts, verification findings, explanation narratives, or numerical context.

## Upload validation

`/ocr`, `/extract`, and `/process` implement the following controls before
decoding, OCR, or external-provider input:

1. read in bounded chunks and reject uploads over 10 MiB;
2. allow only PDF, PNG, and JPEG signatures;
3. compare a supplied `Content-Type` with the detected signature;
4. sanitize client filenames for display and never use them as paths;
5. reject malformed, empty, encrypted, or repaired PDFs;
6. bound PDFs to 20 pages and rendered/image data to 20,000,000 pixels; and
7. return safe structured errors without internal paths or stack traces.

Filename extensions and `Content-Type` alone are not trusted. Expensive PDF
rasterization, OCR, and provider calls occur only after these checks.

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

## Reference-data administration boundary

Administration accepts typed invoice and purchase-order facts, not document
bytes, OCR text, provider responses, or verdicts. Each created record stores a
server-generated identifier, client-declared source and external identifier,
creation time, update time, and optional `retention_until` date. Source and
external identifier remain immutable on update so later facts retain their
declared provenance. These fields are metadata, not proof that a source is
trustworthy; operators must admit only approved reference facts.

The boundary validates schemas before opening a write transaction. Each invoice
or purchase order is limited to 200 line items, each import contains at most 500
total records, and a raw JSON import file is limited to 1 MiB before parsing.
Imports apply one explicit `reject`, `skip`, or `replace` conflict policy inside
one transaction. Invalid input or a rejected conflict rolls back the entire
write, and dry runs always roll back.

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

The `veridoc-reference backup` command uses SQLite's online backup API and
atomically replaces the requested backup only after integrity and migration
checks. Restore requires a stopped service, explicit `--confirm-replace`, a
valid source backup, and no live WAL or SHM sidecar. It validates a temporary
sibling copy before atomically replacing the configured database, so a failed
restore leaves the existing database unchanged. Store backups outside the
repository with the same confidentiality, access, retention, encryption, and
disposal controls as the database. The command supplies a mechanism, not a
backup policy or recovery guarantee.

## Current security limitations

Phase 8 authenticates only local reference-data administration with one shared
Bearer token. It has no user accounts, per-operator authorization, token
rotation/revocation service, TLS termination, rate limit, malware scanning,
encrypted storage, secret manager, durable audit log, privacy workflow, provider
data-residency controls, database access control, managed backup policy,
automated retention service, or authenticated review workflow. Public
processing and review routes are still unauthenticated. The request ID and
record timestamps are operational metadata, not an audit trail. The review page
is a local display surface, not a decision or case management system. Tesseract
availability, model selection, provider account controls, and trained-data
selection are deployment responsibilities. The service is not production ready,
enterprise grade, fraud proof, or safe for real documents.
