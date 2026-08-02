# API

The Phase 5 API accepts one bounded invoice image or PDF. `POST /ocr` returns
raw OCR text; `POST /extract` adds typed invoice extraction with page-level
evidence and declared uncertainty; `POST /process` runs the complete typed
workflow and returns findings, explanations, and a deterministic verdict.
`GET /review` is a minimal local page that submits to `/process`.

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

## `GET /health`

Reports that the API process can serve requests. It does not probe OCR or any
future storage and verification services.

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
- PDFs must contain 1 to 20 unencrypted, non-repaired pages.
- Images and rendered PDF pages must not exceed 20,000,000 pixels.
- The declared `Content-Type` must match the validated signature when supplied.
- Client filenames are sanitized for display and never become processing paths.
- Empty, malformed, unsupported, truncated, and limit-exceeding documents are
  rejected before OCR.

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
engine does not return usable confidence values. PDF page text is joined with
a form-feed boundary in the top-level `text` value.

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
| `413` | `upload_too_large`, `image_too_large`, `page_too_large`, `too_many_pages` | A byte, page, or decoded-pixel bound was exceeded. |
| `415` | `unsupported_document`, `unsupported_content_type`, `content_type_mismatch`, `signature_mismatch` | The media type or signature is unsupported or inconsistent. |
| `422` | `ocr_processing_failed` | A validated document could not be rendered or processed. |
| `503` | `ocr_unavailable` | Tesseract or its configured language data is unavailable. |

## `POST /extract`

Validates the same multipart `file` upload as `/ocr`, runs the configured OCR
baseline, sends normalized OCR text and in-memory PNG page images to the
configured OpenAI Responses adapter, and returns typed extraction data. The
upload limits, accepted types, and temporary-file lifetime are identical to
`POST /ocr`.

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
Amounts are serialized as decimal strings. `ocr_confidence` is calculated from
the selected OCR baseline, while `extraction_confidence` is provider-reported
and not a verification verdict. Evidence references use a one-based page number,
an `ocr_text` or `page_image` source, and an optional text span. Line items use
the same optional description, product identifier, quantity, unit price, total
price, and evidence fields.

### Error responses

`/extract` returns the same validation and OCR error envelopes as `/ocr`, plus:

| Status | Code | Meaning |
| --- | --- | --- |
| `422` | `extraction_processing_failed` | The provider did not return valid structured extraction data. |
| `503` | `extraction_unavailable` | Required provider configuration is missing or the provider cannot be used safely. |

## `POST /process`

Validates the same multipart `file` upload as `/extract`, runs OCR, structured
extraction, deterministic verification, evidence-grounded explanation, and
deterministic verdict derivation. The upload limits, accepted media types, and
temporary-file lifetime are identical to `/ocr` and `/extract`.

### Required configuration

`/process` requires the same non-empty extraction-provider settings as
`/extract`. It uses an optional explanation provider when those settings are
available; absent explanation settings result in deterministic explanations,
not an error. It also opens and initializes a local SQLite reference-data file:

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
| `503` | `reference_data_unavailable` | The configured local reference data could not be opened safely. |

## `GET /review`

Serves a small local HTML page for submitting one document to `/process` and
viewing the returned verdict, extraction evidence, findings, and explanations.
It has no server-side review queue, session, approval control, or saved review
record. Use only fictional or otherwise approved documents.

## Current limitations

The API has no authentication, versioned URL prefix, request correlation
middleware, public reference-data management, standalone verification or
explanation endpoint, approval action, or persistent review record. `/process`
is synchronous and does not treat `clear` as approval or a guarantee that a
document is trustworthy. It is a local development boundary and is not ready
for real documents or production traffic.
