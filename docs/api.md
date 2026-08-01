# API

The Phase 1 API accepts one bounded invoice image or PDF and returns raw OCR
text. It does not extract structured fields, compare purchase orders, detect
anomalies, or produce a verdict.

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

## Current limitations

The API has no authentication, versioned URL prefix, request correlation
middleware, persistent storage, structured invoice extraction, LLM integration,
purchase-order comparison, anomaly detection, explanation layer, or review UI.
It is a local Phase 1 OCR boundary and is not ready for real documents or
production traffic.
