# API

The document-processing API accepts one bounded invoice image or PDF. `POST /ocr` returns
raw OCR text; `POST /extract` adds typed invoice extraction with page-level
evidence and declared uncertainty; `POST /process` runs the complete typed
workflow and returns findings, explanations, and a deterministic verdict.
`GET /review` is a minimal local page that submits to `/process`. Phase 8 also
provides token-authenticated local reference-data administration under
`/admin/reference-data`.

## Local base URL

Start the service:

```bash
uv run uvicorn veridoc.app:app --reload
```

The default local base URL is:

```text
http://127.0.0.1:8000
```

FastAPI also exposes generated local documentation at `/docs`, `/redoc`, and
the OpenAPI document at `/openapi.json`.

## Request correlation

Every response includes an `X-Request-ID` header. Clients may provide a safe
identifier containing 1 to 128 letters, digits, periods, underscores, or
hyphens; otherwise the service generates a 32-character hexadecimal value.
Record this header when reporting a request failure. It identifies operational
metadata only and is not a document, user, or review identifier.

Unexpected application failures return status `500` with the safe code
`internal_server_error` and the same correlation header; internal exception
messages are never returned.

## `GET /health`

Reports that the API process can serve requests. It does not probe Tesseract,
the extraction provider, or local reference data.

### Successful response

Status: `200 OK`

```json
{
  "status": "ok"
}
```

The response uses the required OpenAPI schema `HealthResponse`.

## `POST /ocr`

Validates one multipart upload, rasterizes PDF pages when necessary, runs the
configured Tesseract baseline, and returns raw page text. The multipart field
is named `file`.

### Accepted input and limits

- PDF, PNG, and JPEG signatures are supported.
- The upload is read in bounded chunks and must not exceed 10 MiB.
- The complete multipart request is rejected before parsing when it exceeds the
  file limit plus a 64 KiB framing allowance, including streams without a
  `Content-Length` header.
- PDFs must contain 1 to 20 unencrypted, non-repaired pages.
- Images and individual rendered PDF pages must not exceed 20,000,000 pixels;
  all rendered pages in one PDF must not exceed 50,000,000 pixels in aggregate.
- The declared `Content-Type` must match the validated signature when supplied.
- Client filenames are sanitized for display and never become processing paths.
- Empty, malformed, unsupported, truncated, and limit-exceeding documents are
  rejected before OCR, including PDFs that fail during page inspection.
- Validation and upload closure finish before OCR, provider, processing-service,
  or repository dependencies are constructed.

The service keeps the validated bytes in a private temporary directory only for
the processing lifetime and removes the directory on success or failure.

### Request

```bash
curl.exe -X POST http://127.0.0.1:8000/ocr \
  -F "file=@fictional-invoice.png;type=image/png"
```

PowerShell using the same multipart request:

```powershell
curl.exe -X POST http://127.0.0.1:8000/ocr `
  -F "file=@fictional-invoice.png;type=image/png"
```

### Successful response

Status: `200 OK`

```json
{
  "media_type": "image/png",
  "text": "Fictional Northwind Supplies\nInvoice INV-0001\nTotal 132.00 USD",
  "confidence": 91.5,
  "pages": [
    {
      "page_number": 1,
      "text": "Fictional Northwind Supplies\nInvoice INV-0001\nTotal 132.00 USD",
      "confidence": 91.5
    }
  ]
}
```

`confidence` is an optional mean of Tesseract word confidences. It is not a
calibrated probability and is not a verification verdict. It is `null` when the
engine does not return a finite value from 0 through 100. Malformed OCR engine
page results are rejected with `ocr_processing_failed`. PDF page text is joined
with a form-feed boundary in the top-level `text` value.

### Error responses

Errors use a small safe envelope and do not expose paths, stack traces, raw
document bytes, or OCR engine output:

```json
{
  "detail": {
    "code": "content_type_mismatch",
    "message": "The declared content type does not match the document signature."
  }
}
```

| Status | Codes | Meaning |
| --- | --- | --- |
| `400` | `empty_upload`, `malformed_document`, `empty_document`, `unsupported_pdf` | The document cannot be accepted safely. |
| `413` | `upload_too_large`, `image_too_large`, `page_too_large`, `document_too_large`, `too_many_pages` | A body, file, page, or decoded-pixel bound was exceeded. |
| `415` | `unsupported_document`, `unsupported_content_type`, `content_type_mismatch`, `signature_mismatch` | The media type or signature is unsupported or inconsistent. |
| `422` | `ocr_processing_failed` | A validated document could not be rendered or processed. |
| `503` | `ocr_unavailable` | Tesseract, its configured language data, or its language/timeout configuration is unavailable or invalid. |

## `POST /extract`

Validates the same multipart `file` upload as `/ocr`, runs the configured OCR
baseline, sends normalized OCR text and in-memory PNG page images to the
configured OpenAI Responses adapter, and returns typed extraction data. The
upload limits, accepted types, and temporary-file lifetime are identical to
`POST /ocr`.

OCR text and normalized page images are created off the async request loop. The
aggregate normalized PNG bundle is limited to 32 MiB before provider input; an
excess is returned as the safe `ocr_processing_failed` response.

### Required configuration

Set these non-empty process environment variables before calling `/extract`:

| Variable | Purpose |
| --- | --- |
| `OPENAI_API_KEY` | OpenAI API credential; never commit it. |
| `VERIDOC_LLM_MODEL` | A current vision-capable model available through the Responses API. |

The application does not load `.env` files. Missing configuration and provider
availability failures return a safe `503` response.

### Request

```bash
curl.exe -X POST http://127.0.0.1:8000/extract \
  -F "file=@fictional-invoice.png;type=image/png"
```

### Successful response

Status: `200 OK`

```json
{
  "document_type": "invoice",
  "vendor_name": "Fictional Supplies Ltd.",
  "vendor_identifier": null,
  "invoice_number": "INV-001",
  "purchase_order_number": null,
  "invoice_date": null,
  "due_date": null,
  "currency": "USD",
  "subtotal": null,
  "tax": null,
  "discount": null,
  "total": "18400.00",
  "payment_terms": null,
  "line_items": [],
  "ocr_confidence": 91.0,
  "extraction_confidence": 84.0,
  "evidence": {
    "invoice_number": [
      {
        "page_number": 1,
        "source": "ocr_text",
        "text_span": "Invoice No: INV-001"
      }
    ]
  },
  "uncertainties": []
}
```

`document_type` is `invoice`, `purchase_order`, or `unknown`. Invoice fields
that are not visible are `null`; they are never invented to fill the schema.
Amounts and quantities are serialized as decimal strings and accept at most 24
digits with no more than 6 decimal places. `ocr_confidence` is calculated from
the selected OCR baseline, while `extraction_confidence` is provider-reported
and not a verification verdict. Evidence references use a one-based page number,
an `ocr_text` or `page_image` source, and an optional text span. Every referenced
page must exist in the OCR request. When an `ocr_text` span is supplied, its
non-empty Unicode-normalized, case-folded, whitespace-collapsed value must occur
on that page. Line items use the same optional description, product identifier,
quantity, unit price, total price, and evidence rules.

### Error responses

`/extract` returns the same validation and OCR error envelopes as `/ocr`, plus:

| Status | Code | Meaning |
| --- | --- | --- |
| `422` | `extraction_processing_failed` | The provider did not return valid structured extraction data. |
| `503` | `extraction_unavailable` | Required provider configuration is missing, the provider times out after the bounded application deadline, or the provider cannot be used safely. |

## `POST /process`

Validates the same multipart `file` upload as `/extract`, runs OCR, structured
extraction, deterministic verification, evidence-grounded explanation, and
deterministic verdict derivation. The upload limits, accepted media types, and
temporary-file lifetime are identical to `/ocr` and `/extract`.

### Required configuration

`/process` requires the same non-empty extraction-provider settings as
`/extract`. The current extraction and explanation adapters share those
settings, so missing configuration fails the required extraction stage. After
valid extraction configuration exists, explanation-provider unavailability or
rejected or malformed guidance—including a provider timeout—falls back to
deterministic explanations. `/process` also opens and initializes a local SQLite
reference-data file:

| Variable | Default | Purpose |
| --- | --- | --- |
| `OPENAI_API_KEY` | none | Required credential for structured extraction. |
| `VERIDOC_LLM_MODEL` | none | Required vision-capable Responses API model for extraction. |
| `VERIDOC_REFERENCE_DATABASE` | `veridoc-reference.sqlite3` | Local SQLite invoice/PO reference-data path. |

Reference data must be fictional or otherwise approved. `/process` does not
seed, manage, export, or persist the uploaded document into that database.

### Request

```bash
curl.exe -X POST http://127.0.0.1:8000/process \
  -H "X-Request-ID: local-process-example-001" \
  -F "file=@fictional-invoice.png;type=image/png"
```

### Successful response

Status: `200 OK`

The response has four typed sections. `extraction` uses the same complete
schema as `/extract`, including its evidence map. The abbreviated example below
omits unrelated nullable and repeated nested fields for readability:

```json
{
  "extraction": {
    "document_type": "invoice",
    "vendor_name": "Fictional Supplies Ltd.",
    "invoice_number": "INV-001",
    "evidence": {
      "invoice_number": [
        {
          "page_number": 1,
          "source": "ocr_text",
          "text_span": "Invoice No: INV-001"
        }
      ]
    }
  },
  "findings": [
    {
      "finding_type": "duplicate_invoice_number",
      "severity": "high",
      "explanation": "This vendor already has an invoice with the extracted invoice number.",
      "comparison_source": "invoice_register",
      "deterministic_rule": "invoice_number must be unique within a vendor history",
      "observed_value": "INV-001"
    }
  ],
  "explanations": [
    {
      "finding": {
        "finding_type": "duplicate_invoice_number"
      },
      "narrative": "Review the existing invoice record before proceeding.",
      "numerical_context": "Observed value: INV-001. Expected value: no existing invoice with this number.",
      "source": "deterministic"
    }
  ],
  "verdict": {
    "status": "review_required",
    "summary": "1 deterministic verification finding requires review.",
    "finding_count": 1,
    "highest_severity": "high"
  }
}
```

`findings` are canonical deterministic verification values. Each explanation
contains its canonical finding and application-rendered numerical context.
`verdict.status` is `review_required` when findings exist and `clear` when they
do not. `clear` is not approval or a guarantee that the invoice is trustworthy.

### Error responses

`/process` returns the validation, OCR, and extraction errors documented above,
plus:

| Status | Code | Meaning |
| --- | --- | --- |
| `422` | `processing_failed` | The complete workflow did not produce a typed result. |
| `503` | `reference_data_unavailable` | The configured local reference data could not be opened or decoded under the persisted-data contract safely. |

## Reference-data administration

Phase 8 provides local CRUD and bounded import routes for approved historical
invoice and purchase-order facts. These routes never accept or return uploaded
document bytes, OCR text, extraction evidence, model prompts, or credentials.

### Authentication and configuration

Set a dedicated token containing 32 to 256 letters, digits, or the documented
safe token punctuation:

```powershell
$env:VERIDOC_ADMIN_TOKEN = "replace-with-a-random-token-at-least-32-characters"
```

Send it with every administration request:

```text
Authorization: Bearer <VERIDOC_ADMIN_TOKEN>
```

The token is independent of `OPENAI_API_KEY`. Missing or invalid server
configuration returns `503`; missing, malformed, and incorrect request
credentials all return the same `401` response with `WWW-Authenticate: Bearer`.
The shared token has no user identity or role semantics and is not suitable for
remote production administration.

### Record metadata and limits

Every managed record contains:

- a server-generated `record_id`;
- immutable client provenance in `source` and `external_id`;
- server-managed `created_at` and `updated_at` timestamps; and
- an optional `retention_until` date.

`source` is limited to 64 safe identifier characters; `external_id` is limited
to 128. Invoice and purchase-order fields and line-item text are bounded, one
record may contain at most 200 line items, list requests return at most 200
records, and decimal values allow at most 24 digits with 6 decimal places.
`retention_until` is metadata for operator policy; Phase 8 does not delete a
record automatically when the date passes.

Every invoice and purchase-order `vendor_key` is case-folded, runs of separator
characters or underscores become one hyphen, and surrounding hyphens are
removed. The canonical result must contain 1-128 characters. The optional
`vendor_key` list filters apply the same normalization, so a query such as
`Fictional Supplies` matches the stored key `fictional-supplies`.

### CRUD routes

Invoice and purchase-order create/update JSON request bodies are limited to
1 MiB before parsing.

List requests accept a non-negative `offset` no greater than SQLite's signed
64-bit maximum (`9,223,372,036,854,775,807`), and a `limit` of at most 200.

| Method and path | Result |
| --- | --- |
| `POST /admin/reference-data/invoices` | Create one managed invoice; returns `201`. |
| `GET /admin/reference-data/invoices` | List invoices with optional `vendor_key`, `offset`, and `limit`. |
| `GET /admin/reference-data/invoices/{record_id}` | Fetch one invoice. |
| `PUT /admin/reference-data/invoices/{record_id}` | Replace invoice facts and retention while preserving provenance. |
| `DELETE /admin/reference-data/invoices/{record_id}` | Delete one invoice and its line items; returns `204`. |
| `POST /admin/reference-data/purchase-orders` | Create one managed purchase order; returns `201`. |
| `GET /admin/reference-data/purchase-orders` | List purchase orders with optional `vendor_key`, `offset`, and `limit`. |
| `GET /admin/reference-data/purchase-orders/{record_id}` | Fetch one purchase order. |
| `PUT /admin/reference-data/purchase-orders/{record_id}` | Replace PO facts and retention while preserving provenance. |
| `DELETE /admin/reference-data/purchase-orders/{record_id}` | Delete one PO and its line items; returns `204`. |

Create an invoice:

```powershell
$headers = @{ Authorization = "Bearer $env:VERIDOC_ADMIN_TOKEN" }
$body = @{
  metadata = @{
    source = "approved-fixture"
    external_id = "invoice-2026-001"
    retention_until = "2027-12-31"
  }
  invoice = @{
    vendor_key = "fictional-supplies"
    invoice_number = "INV-001"
    currency = "USD"
    total = "42.00"
  }
} | ConvertTo-Json -Depth 6

Invoke-RestMethod -Method Post `
  -Uri http://127.0.0.1:8000/admin/reference-data/invoices `
  -Headers $headers -ContentType application/json -Body $body
```

Create requests conflict when the same record type already owns the supplied
`source` plus `external_id`. Purchase orders also conflict on duplicate
`vendor_key` plus `purchase_order_number`.

### Bounded atomic import

`POST /admin/reference-data/import` accepts one multipart `file` with
`application/json`. The service reads at most 1 MiB before parsing, accepts at
most 500 combined invoice and purchase-order records, validates the complete
batch, and then uses one SQLite transaction.

Query parameters:

| Parameter | Values | Default | Meaning |
| --- | --- | --- | --- |
| `dry_run` | `true`, `false` | `false` | Execute validation and conflict logic, then roll back. |
| `conflict` | `reject`, `skip`, `replace` | `reject` | Select behavior for matching provenance. |

`replace` updates only a record with matching `source` and `external_id`; it
does not take over a purchase-order natural key owned by different provenance.
Any rejected conflict rolls back the entire batch.

```powershell
curl.exe -X POST `
  "http://127.0.0.1:8000/admin/reference-data/import?dry_run=true&conflict=reject" `
  -H "Authorization: Bearer $env:VERIDOC_ADMIN_TOKEN" `
  -F "file=@fictional-reference-data.json;type=application/json"
```

A successful response reports `dry_run`, `created`, `replaced`, and `skipped`
counts. It does not return the imported records.

### Administration errors

| Status | Code | Meaning |
| --- | --- | --- |
| `401` | `invalid_admin_credentials` | The Bearer credential is missing, malformed, or incorrect. |
| `404` | `reference_record_not_found` | The requested server record identifier does not exist. |
| `409` | `reference_data_conflict` | Provenance or a protected PO natural key conflicts. |
| `413` | `reference_data_request_too_large` | A create/update JSON body exceeds 1 MiB. |
| `413` | `reference_data_import_too_large` | The import exceeds 1 MiB. |
| `415` | `unsupported_import_media_type` | The import is not declared as `application/json`. |
| `422` | `invalid_reference_data_import` | Import JSON or its typed records are invalid. |
| `503` | `admin_authentication_unavailable` | No valid server administration token is configured. |
| `503` | `reference_data_unavailable` | The configured SQLite data cannot be opened, migrated, or decoded under the persisted-data contract safely. |

The complete multipart import request is also bounded before parsing to the
1 MiB file limit plus a 64 KiB framing allowance.

## `GET /review`

Serves a small local HTML page for submitting one document to `/process` and
viewing the returned verdict, extraction evidence, findings, and explanations.
It has no server-side review queue, session, approval control, or saved review
record. Use only fictional or otherwise approved documents.

## Current limitations

Only the local reference-data administration routes are authenticated. The API
has no user accounts, roles, versioned URL prefix, standalone verification or
explanation endpoint, approval action, persistent audit trail, or persistent
review record. `/process` is synchronous and does not treat `clear` as approval
or a guarantee that a document is trustworthy. The shared admin token does not
make this local development boundary ready for real documents or production
traffic.
