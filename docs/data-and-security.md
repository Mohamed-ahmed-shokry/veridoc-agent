# Data and Security

Veridoc will process commercially sensitive documents in later phases. Treat
every document, extracted field, reference record, model response, and serialized
artifact as untrusted or sensitive at its boundary.

Phase 0 accepts no documents, stores no reference data, and calls no external
service. The policies below constrain future approved work; they do not claim
those controls are implemented yet.

## Allowed development data

Commit only:

- synthetic invoices and purchase orders;
- fictional vendor histories;
- deterministic programmatically generated fixtures; or
- appropriately licensed subsets of public datasets such as SROIE or CORD.

For a public subset, record its source, license, selected files, and any required
attribution beside the fixture-generation instructions. Do not assume that a
publicly downloadable document is licensed for redistribution.

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

Future fixture generators must produce fictional data from a fixed seed or
fully specified inputs. Keep fixtures small and tailored to one scenario, such
as a valid invoice, an arithmetic mismatch, or an insufficient-history case.

Generation must not call production services or sample local documents. A
fixture change belongs with its focused test or in a separate reviewable fixture
commit when substantial. Generated fixtures should include assertions for their
schema and expected evidence so accidental drift is visible.

Phase 0 contains no document fixtures because no document behavior exists.

## Secrets and environment files

The repository tracks `.env.example` with safe comments only. `.gitignore`
excludes `.env` and `.env.*` while explicitly allowing `.env.example`.

Phase 0 has no required environment variables and does not load `.env`. When a
later phase adds configuration:

- read secrets from the process environment or an approved secret provider;
- validate required settings at startup;
- use unmistakably fake placeholders in `.env.example`;
- never include a real secret in a default, test, exception, or log; and
- document the variable's purpose without documenting its value.

Before committing, inspect staged changes for accidental credentials and verify
that any local `.env` remains ignored.

## Safe logging

Phase 0 relies on Uvicorn's standard lifecycle and request logs. There is no
document-processing logger yet.

Future structured logs may include:

- a generated request or document correlation identifier;
- the processing stage;
- a safe error category;
- duration and retryability; and
- non-sensitive counts or limits needed for diagnosis.

Logs must exclude complete documents, OCR text, extracted names or identifiers,
line items, secrets, authorization headers, database URLs, raw model prompts and
responses, local temporary paths, and stack traces returned to clients.

## Upload validation — planned for Phase 1

No upload endpoint exists in Phase 0. Before accepting an invoice, Phase 1 must:

1. allow only explicitly supported PDF, PNG, and JPEG inputs;
2. enforce a bounded streaming size limit before buffering or parsing;
3. compare the declared type with a validated content signature;
4. normalize, ignore, or replace unsafe client filenames;
5. bound PDF page count and decoded image dimensions or pixels;
6. reject empty, malformed, encrypted when unsupported, or decompression-heavy
   inputs with safe errors;
7. perform expensive decoding and OCR only after cheap validation; and
8. test mismatch, truncation, oversize, malformed, and cleanup paths.

Do not rely on filename extensions or `Content-Type` alone.

## Temporary files and generated artifacts

Phase 0 creates no application temporary files. The repository-relative paths
`tmp/uploads/`, `uploads/`, `ocr-artifacts/`, and `artifacts/ocr/` are ignored to
reduce the risk of committing later development artifacts; ignore rules are not
a security control.

When temporary files become necessary:

- use an OS- or application-owned private temporary directory;
- generate server-side names instead of trusting upload names;
- restrict access to the processing lifetime and worker that needs the file;
- close resources and delete files on success, validation failure, cancellation,
  and unexpected exceptions;
- avoid persistent copies unless retention is explicitly approved; and
- never expose an internal path in an API response.

## Retention assumptions

Phase 0 retains nothing because it accepts no documents. Version 1 should assume
uploaded document bytes and derived OCR images are ephemeral for one processing
request unless a later approved requirement defines storage and retention.

SQLite reference data in Phase 3 will be synthetic for development. Any future
production retention, deletion, backup, access-control, and audit requirements
must be designed and approved before production data is introduced.

## Current limitations

The scaffold has no authentication, authorization, TLS termination, rate limit,
request correlation middleware, upload validation, malware scanning, encrypted
storage, secret manager, audit log, data retention service, or privacy workflow.
The only route is the non-sensitive `GET /health` endpoint.

These omissions are acceptable for the local Phase 0 scaffold and mean Veridoc
must not be described as production ready, enterprise grade, fraud proof, or
safe for real documents.
