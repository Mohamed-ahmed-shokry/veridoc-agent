# 0002: Use the OpenAI Responses API for Phase 2 extraction

## Status

Accepted

## Context

Phase 2 needs a vision-capable model to classify invoices or purchase orders,
interpret layouts, extract typed fields, and attach page-level evidence. The
model must receive both OCR text and rendered page images, remain replaceable,
and return data validated against the invoice schema. Phase 2 does not include
verification or persistence.

## Decision

Use the OpenAI Python SDK's [Responses API](https://platform.openai.com/docs/api-reference/responses)
structured parsing path behind the `StructuredExtractor` protocol. The adapter
uses a configurable vision-capable model from `VERIDOC_LLM_MODEL`, an API key
from `OPENAI_API_KEY`, OCR page text, and in-memory PNG page images. It requests
the `InvoiceExtraction` Pydantic schema, does not persist responses through the
API, replaces any model-supplied OCR confidence with the deterministic OCR
aggregate, and maps provider or invalid-output failures to safe typed errors.

## Alternatives considered

- Directly couple FastAPI routes to the OpenAI SDK.
- Use a generic JSON response and manually parse it in the API layer.
- Use a local vision model or deterministic template parser before evaluation
  demonstrates that the selected vision approach is insufficient.
- Defer visual inputs and extract only from raw OCR text.

## Consequences

The adapter can be replaced without changing the graph or API service, and
tests mock it without credentials or network access. A configured external
provider is required for `/extract`; document text and rendered pages cross that
provider boundary for the request lifetime. The API must surface uncertainty and
evidence without treating model confidence as a verification result. Arithmetic,
historical comparisons, anomaly detection, explanations, and verdicts remain
out of scope until their later phases are approved.
