# Data and Security

Veridoc processes commercially sensitive documents at an untrusted boundary.
Phase 1 now accepts document bytes for one ephemeral OCR request, but it is
still a local development service and must not receive real invoices or
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

Phase 1 tests use generated fictional invoice bytes from
`tests/fixtures/fictional_invoice.py`; no source document is checked in.

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
small and tailored to one scenario. The Phase 1 fixture generator is deterministic
and contains only fictional vendor, invoice, purchase-order, and total text.

Generation must not call production services or sample local documents. A
fixture change belongs with its focused test or in a separate reviewable fixture
commit when substantial. Generated fixtures should include assertions for
determinism and expected behavior so accidental drift is visible.

## Secrets and environment files

The repository tracks `.env.example` with safe comments only. `.gitignore`
excludes `.env` and `.env.*` while explicitly allowing `.env.example`.

Phase 1 reads only optional `TESSERACT_CMD` and `TESSERACT_LANG` values from the
process environment; it does not load `.env` files. Keep executable paths and
language choices out of committed secrets and use unmistakably fake placeholders
in `.env.example` when examples are needed.

Before committing, inspect staged changes for accidental credentials and verify
that any local `.env` remains ignored.

## Safe logging

Phase 1 relies on Uvicorn's standard lifecycle and request logs. The application
does not log complete documents, raw OCR text, extracted names or identifiers,
line items, credentials, authorization headers, raw Tesseract output, or local
temporary paths. Future processing logs may include only a generated correlation
identifier, stage, safe error category, duration, and retryability.

## Upload validation

The `/ocr` endpoint implements the following controls before decoding or OCR:

1. read in bounded chunks and reject uploads over 10 MiB;
2. allow only PDF, PNG, and JPEG signatures;
3. compare a supplied `Content-Type` with the detected signature;
4. sanitize client filenames for display and never use them as paths;
5. reject malformed, empty, encrypted, or repaired PDFs;
6. bound PDFs to 20 pages and rendered/image data to 20,000,000 pixels; and
7. return safe structured errors without internal paths or stack traces.

Filename extensions and `Content-Type` alone are not trusted. Expensive PDF
rasterization and OCR occur only after these checks.

## Temporary files and retention

Validated upload bytes are written to a private OS temporary directory with a
server-generated filename for the processing lifetime. The file and directory
are removed on success, validation failure, OCR failure, cancellation, and
unexpected exceptions through the context-managed storage boundary.

Phase 1 retains no uploaded document, rendered page, or OCR artifact. The
repository-relative paths `tmp/uploads/`, `uploads/`, `ocr-artifacts/`, and
`artifacts/ocr/` remain ignored as defense against accidental future artifacts;
ignore rules are not a security control.

## Current security limitations

Phase 1 has no authentication, authorization, TLS termination, rate limit,
request-correlation middleware, malware scanning, encrypted storage, secret
manager, audit log, or privacy workflow. Tesseract executable availability and
trained-data selection are deployment responsibilities. The service is not
production ready, enterprise grade, fraud proof, or safe for real documents.
