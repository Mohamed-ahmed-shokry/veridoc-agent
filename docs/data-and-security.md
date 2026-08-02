# Data and Security

Veridoc processes commercially sensitive documents at an untrusted boundary.
Phase 5 accepts document bytes for one ephemeral OCR, extraction, or complete
processing request. Complete processing reads and writes local reference facts
at an explicitly configured SQLite path, but never persists the current upload.
When `/extract` or `/process` is used, the extraction adapter sends the current
request's OCR text and normalized page images to the configured OpenAI provider.
The internal explanation adapter sends only canonical verification findings,
never document bytes, page images, or raw OCR text. The local `/review` page
submits the selected document to `/process` without retaining it in the page.
This is still a local development service and must not receive real invoices or
production data.

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
synthetic boundaries; no browser upload or reference database is committed.

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
the optional `VERIDOC_REFERENCE_DATABASE` path used by `/process`, from the
process environment; it does not load `.env` files. Keep executable paths,
model names, language choices, and local database paths out of committed
secrets, and use unmistakably fake placeholders in `.env.example` when examples
are needed.

Before committing, inspect staged changes for accidental credentials and verify
that any local `.env` remains ignored.

## Safe logging

The application relies on Uvicorn's standard lifecycle and request logs. It does
not log complete documents, raw OCR text, rendered pages, extracted names or
identifiers, line items, credentials, authorization headers, raw Tesseract
output, provider responses, local temporary paths, persisted reference facts, or
verification findings, explanation narratives, or numerical context. Future logs
may include
only a generated correlation identifier, stage, safe error category, duration,
and retryability.

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

## Local reference-data retention

`SQLiteInvoiceRepository` persists invoice and purchase-order reference fields
only at `VERIDOC_REFERENCE_DATABASE` (or the local default
`veridoc-reference.sqlite3`) when `/process` is configured. It does not persist
document bytes, OCR text, page images, evidence spans, credentials, provider
responses, explanations, or final verdicts. Never seed it with real data in this
local Phase 5 stage. The project ignores `*.db`, `*.sqlite`, and `*.sqlite3` as
defense against accidental commits; ignore rules do not encrypt data, set
retention periods, control backups, or authorize storage.

No API endpoint creates, exports, deletes, or exposes reference data in Phase 5;
the repository schema is initialized locally only to support deterministic
lookups. If a local database is no longer needed, remove it only after confirming
its path and retention requirements. Future deployment work must add access
control, encryption, backup, lifecycle, and audit policies before handling real
data.

## Current security limitations

Phase 5 has no authentication, authorization, TLS termination, rate limit,
request-correlation middleware, malware scanning, encrypted storage, secret
manager, audit log, privacy workflow, provider data-residency controls, database
access control, backup policy, retention service, or authenticated review
workflow. The review page is a local display surface, not a decision or case
management system. Tesseract availability, model selection, provider account
controls, and trained-data selection are deployment responsibilities. The service
is not production ready, enterprise grade, fraud proof, or safe for real
documents.
