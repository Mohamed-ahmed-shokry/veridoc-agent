# API

The Phase 0 API exposes process health only. It does not accept or process
documents.

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

Reports that the API process can serve requests. It deliberately does not probe
OCR, LLM, storage, or database dependencies because none are implemented in
Phase 0.

### Request

The endpoint has no path parameters, query parameters, authentication, or
request body.

```http
GET /health HTTP/1.1
Host: 127.0.0.1:8000
Accept: application/json
```

PowerShell example:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Command Prompt, PowerShell, or shell example using the curl executable:

```bash
curl.exe http://127.0.0.1:8000/health
```

### Successful response

Status: `200 OK`

Content type: `application/json`

Schema: `HealthResponse`

| Field | Type | Required | Meaning |
| --- | --- | --- | --- |
| `status` | string literal `ok` | yes | The API process is available |

Response body:

```json
{
  "status": "ok"
}
```

The named schema is published in OpenAPI and enforced by FastAPI's response
model.

## Error responses

The health endpoint has no input and no expected application-level error. An
unknown path returns FastAPI's standard small JSON response:

Status: `404 Not Found`

```json
{
  "detail": "Not Found"
}
```

No custom error envelope, correlation header, or exception middleware exists in
Phase 0. Later I/O endpoints must document their safe typed errors when they are
implemented.

## Document uploads

There is no upload endpoint in Phase 0. Therefore:

- no request accepts invoice bytes;
- no file type is currently accepted;
- no upload-size or page/pixel limit is currently an API contract; and
- no OCR response exists.

Phase 1 must define supported types, validated signatures, streaming size bounds,
safe filename behavior, document limits, temporary-file handling, and error
responses before documenting an upload request.

## Current limitations

The API has no authentication, versioned URL prefix, document processing,
request correlation identifier, persistent storage, or external-service status.
It is a local development scaffold and is not ready for real documents or
production traffic.
