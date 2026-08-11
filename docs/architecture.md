# Architecture

Veridoc's document-processing boundary accepts one bounded invoice or
purchase-order image/PDF, runs OCR, and returns typed extraction data with
page-level evidence and explicit uncertainty. It also provides local SQLite
reference persistence, deterministic verification services, and an internal
evidence-grounded explanation layer. `POST /process` now orchestrates those
stages into a typed final response and `GET /review` provides a minimal local
review page. Phase 8 adds bearer-token-protected local reference-data CRUD and
bounded atomic import plus offline backup/restore. User identities, roles,
review records, and production deployment controls remain later work.

## System boundary

Veridoc is scoped to invoice and purchase-order reconciliation. It is not a
generic document platform, identity/KYC system, training pipeline, accounting
system of record, or autonomous payment approver.

```mermaid
flowchart LR
    Client["HTTP multipart client"] --> Context["Request correlation"]
    Context --> App["FastAPI application"]
    Context --> RequestLog["Metadata-only request log"]
    App --> Validate["Bounded upload validation"]
    Validate --> ProcessGraph["Typed complete processing graph at POST /process"]
    ProcessGraph --> OCR
    Validate --> Temp["Private temporary file"]
    Temp --> Decode["PNG/JPEG decode or PDF rasterization"]
    Decode --> OCR["OCREngine protocol"]
    OCR --> Tesseract["Tesseract adapter"]
    Tesseract --> Raw["OCRResponse at POST /ocr"]
    Tesseract --> Bundle["OCR text plus in-memory PNG pages"]
    Bundle --> Graph["Typed LangGraph extraction node"]
    Graph --> Extractor["StructuredExtractor protocol"]
    Extractor --> OpenAI["OpenAI Responses adapter"]
    OpenAI --> Typed["InvoiceExtraction at POST /extract"]
    Typed --> VerifyGraph["Typed LangGraph verification node"]
    VerifyGraph --> Verify["VerificationService"]
    Verify --> Repository["InvoiceRepository protocol"]
    SQLite["SQLite reference adapter"] --> Repository
    Verify --> Findings["VerificationResult"]
    Findings --> ExplainGraph["Typed LangGraph explanation node"]
    ExplainGraph --> Explain["ExplanationService"]
    Explain --> Fallback["Deterministic renderer"]
    Explain --> Explainer["FindingExplainer protocol"]
    Explainer --> ExplainOpenAI["OpenAI Responses adapter"]
    Explain --> Explanations["ExplanationResult"]
    Explain --> Verdict["Deterministic verdict node"]
    Verdict --> Processed["ProcessingResult"]
    Reviewer["Local reviewer"] --> Review["GET /review"]
    Review --> ProcessGraph
    Admin["Local reference-data administrator"] --> AdminAuth["Bearer token boundary"]
    AdminAuth --> AdminAPI["Admin CRUD and bounded import router"]
    AdminAPI --> AdminProtocol["ReferenceDataAdminRepository protocol"]
    AdminProtocol --> SQLite
    Import["At most 1 MiB and 500 records"] --> AdminAPI
    Operator["Stopped-service operator"] --> Maintenance["veridoc-reference backup or restore"]
    Maintenance --> SQLite
    Migrations["Forward-only migration ledger"] --> SQLite
```

The outer ASGI boundary limits complete document/import request bodies before
multipart parsing, even without `Content-Length`. Document validation and upload
closure finish before OCR, provider, processing, or repository dependency
construction. Rasterization and OCR run in worker threads. Validated bytes use a
private temporary directory only during processing; page images are normalized
in memory, bounded as a document bundle, and not retained after the request.

## Package boundaries

- `veridoc.app` owns FastAPI routes, request correlation, dependency injection,
  and safe HTTP error translation for `/ocr`, `/extract`, and `/process`.
- `veridoc.ingestion` bounds uploads, validates signatures and decoded limits,
  sanitizes filenames, and manages private temporary uploads.
- `veridoc.ocr` decodes validated documents, invokes the replaceable OCR engine,
  and can return OCR text paired with normalized PNG pages.
- `veridoc.extraction.models` owns strict Pydantic invoice, line-item, evidence,
  uncertainty, and confidence schemas. Optional fields remain optional.
- `veridoc.extraction.protocol` defines the provider-neutral async
  `StructuredExtractor` boundary and validates page/image alignment.
- `veridoc.extraction.graph` compiles the typed Phase 2 graph:
  `START -> extract -> END`.
- `veridoc.extraction.service` composes OCR, the typed extraction request, and
  the graph without importing FastAPI or the OpenAI SDK.
- `veridoc.extraction.openai_responses` implements the protocol with OCR text,
  rendered page images, structured parsing, and safe provider failure mapping.
- `veridoc.persistence.protocol` defines the invoice and purchase-order
  reference-data boundary; `veridoc.persistence.sqlite` implements it with local
  SQLite tables.
- `veridoc.administration` owns bounded CRUD/import schemas, the shared-token
  authentication policy, the administration repository protocol, FastAPI router,
  and local maintenance CLI. It never accepts or returns document content.
- `veridoc.persistence.migrations` owns the ordered SQLite schema ledger;
  `veridoc.persistence.schema` validates required tables, columns, keys,
  constraints, and provenance indexes; `veridoc.persistence.maintenance` owns
  integrity-checked online backup and validated atomic restore.
- `veridoc.verification` owns strict findings, pure arithmetic/history/PO
  comparison rules, an API-neutral service, and a typed single-node verification
  graph. Verification imports the repository protocol, not SQLite connection
  code.
- `veridoc.explanation` owns strict explanation result and provider-draft
  schemas, a deterministic renderer, provider-draft validation, an API-neutral
  service, and a typed single-node explanation graph. It receives verification
  findings, not OCR or document data.
- `veridoc.explanation.openai_responses` implements the optional provider
  boundary. It can propose short guidance only; application code retains the
  canonical finding and renders all numerical context.
- `veridoc.processing` owns the typed complete graph, its API-neutral service,
  final result contract, and deterministic review verdict. It orchestrates
  approved stages but does not implement their domain rules.
- `veridoc.review` renders the no-build local review page. It submits to the
  public processing endpoint and never stores a document or review decision.

## Typed extraction flow

`OCRService.process_with_page_images` produces an `OCRDocumentBundle` containing
the typed OCR result and one numbered in-memory PNG image per OCR page.
`ExtractionRequest` rejects nonmatching page sequences. The graph's
`ExtractionState` is a `TypedDict` with a required request and optional typed
`InvoiceExtraction` output; no node exchanges a loose undocumented dictionary.

The response supports invoice/purchase-order/unknown classification, nullable
header fields, nullable line-item values, confidence values, evidence keyed by
field name, and explicit uncertainty. `ocr_confidence` is calculated by the OCR
boundary and overrides any provider-supplied value. `extraction_confidence` is a
provider-reported signal, not a calibrated probability or verification verdict.
Evidence is deliberately limited to page number, OCR-or-image source, and an
optional text span. Stable bounding-box coordinates are not an implemented
contract.

## Typed verification flow

`VerificationService` accepts an `InvoiceExtraction` and an `InvoiceRepository`.
It returns a `VerificationResult` containing one structured finding per failed
deterministic rule, rather than an opaque score. Findings carry observed and
expected values or ranges, comparison source, rule, severity, and historical
statistics when applicable. The typed `VerificationState` graph is
`START -> verify -> END` and is separate from Phase 2 extraction orchestration.

The service checks arithmetic, invoice-date ordering, duplicate invoice numbers,
purchase-order headers and line items, vendor total/line-item history, line-item
occurrence, and consistently observed payment terms. It uses a minimum of three
same-currency observations for statistical comparisons and reports
`insufficient_history` instead of treating smaller samples as reliable.

## Typed explanation flow

`ExplanationService` accepts a `VerificationResult` and produces an
`ExplanationResult` with one `FindingExplanation` per finding. Each explanation
always carries the original typed finding and deterministic numerical context
rendered only from that finding's observed value, expected value or range,
sample size, mean, standard deviation, and z-score.

The typed `ExplanationState` graph is `START -> explain -> END`. Its optional
`FindingExplainer` receives the canonical findings alone and may propose a
short action-oriented narrative. The service accepts a provider result only
when it covers every finding exactly once and contains no numeric, comparative,
or negated factual claim. Otherwise, including provider unavailability or
invalid structured output, it returns the deterministic explanation instead.

## Typed complete processing flow

`ProcessingService` accepts one `ValidatedUpload` and invokes a typed
`ProcessingState` graph: `START -> ocr -> extract -> verify -> explain ->
verdict -> END`. The graph reuses the Phase 2, Phase 3, and Phase 4 typed
graphs rather than reimplementing extraction, verification, or explanation
logic.

`ProcessingResult` returns the `InvoiceExtraction` (including its page-level
evidence), ordered canonical findings, ordered explanations, and a
`ProcessingVerdict`. A verdict is `review_required` whenever at least one
finding exists; otherwise it is `clear`, meaning only that no deterministic
finding requires review. It is not an approval, payment decision, or guarantee
that the document is trustworthy. See [ADR 0005](decisions/0005-use-review-required-processing-verdicts.md).

## Dependency direction

```text
FastAPI route --> extraction service --> typed graph and protocols
                                              ^
                                              |
                         OCR and OpenAI adapters implement boundaries

verification service --> repository protocol <-- SQLite adapter

admin API --> authentication --> administration repository protocol <-- SQLite adapter
    |
    +--> bounded import validation --> one SQLite transaction

maintenance CLI --> SQLite online backup / migrated atomic restore

explanation service --> finding-explainer protocol <-- OpenAI adapter
                       |
                       +--> deterministic renderer

processing service --> processing graph --> extraction, verification, and explanation graphs
review page --> POST /process
```

API code does not implement extraction or verification rules. The extraction,
explanation, and processing services do not import FastAPI or an OpenAI SDK.
Verification and explanation domain logic must not import FastAPI, LangGraph,
SQLite connection code, or vendor SDKs.

## Planned evolution boundaries

The [project roadmap](roadmap.md) describes later candidates without approving
their implementation. If those phases are approved, they must extend the
current boundaries rather than bypass them:

- persistent review records must preserve canonical findings, explanations, and
  verdicts rather than mutating them into reviewer-approved facts;
- deployment controls such as user authentication, secret management, TLS,
  automated retention, and observability export must remain outside
  deterministic domain rules; and
- evaluation must report OCR/extraction quality separately from deterministic
  verification-rule coverage and end-to-end operational performance.

Phases 9 through 11 remain unapproved and unimplemented.

## External boundaries

### OCR

Tesseract remains the version 1 OCR baseline behind `OCREngine`. It receives one
decoded Pillow image and returns typed page text plus optional aggregate word
confidence. See [ADR 0001](decisions/0001-use-tesseract-for-v1.md) for its
installation, Arabic/Latin configuration, and limitations.

### Structured extraction

`OpenAIResponsesExtractor` is configured with `OPENAI_API_KEY` and
`VERIDOC_LLM_MODEL` when `/extract` is called. It passes labeled OCR text and
high-detail in-memory PNG page images through the Responses API's Pydantic
structured-parsing path with response storage disabled. The adapter returns a
typed result, or raises a safe unavailable/invalid-output error. See
[ADR 0002](decisions/0002-use-openai-responses-for-phase-2.md).

The adapter is replaced in tests with a fake implementation. Tests never need
credentials, network access, or a Tesseract executable.

### Persistence and verification

`SQLiteInvoiceRepository` applies numbered forward-only migrations for vendor
invoices, purchase orders, line items, and administrative metadata. Amounts are
stored as text and recreated as `Decimal`; dates and timestamps use ISO-8601
text. `POST /process` and the administration adapter open the path in
`VERIDOC_REFERENCE_DATABASE`, defaulting to `veridoc-reference.sqlite3`.
SQLite and unsupported-schema failures map to a safe unavailable error.
Initialization also validates the current primary keys, required `NOT NULL`
columns, child foreign keys, purchase-order natural uniqueness, and managed
record/provenance indexes after migration.

The separate `ReferenceDataAdminRepository` protocol exposes bounded pages,
provenance-preserving CRUD, and one-transaction imports. Provenance identity is
`source` plus `external_id` within each record type. A server `record_id` and
creation/update timestamps are application managed. Optional retention dates
are metadata only; no background deletion service exists.

`veridoc-reference` performs online backup and stopped-service restore without
an HTTP database export. Both destination replacements refuse live WAL, SHM,
or rollback-journal sidecars. Restore validates the source, migrates a temporary
sibling database, validates database and foreign-key integrity plus structural
invariants again, and atomically replaces the destination. See
[ADR 0003](decisions/0003-use-sqlite-for-phase-3-reference-data.md) and
[ADR 0007](decisions/0007-use-forward-only-sqlite-migrations.md).

Administration authentication uses a dedicated 32-256 character token from
`VERIDOC_ADMIN_TOKEN`, not an OpenAI credential. The application compares the
presented Bearer value in constant time and never logs it. This is a shared local
secret without users or roles; see
[ADR 0006](decisions/0006-use-bearer-token-for-local-administration.md).

Verification rules are deterministic Python code. Statistical findings use
Decimal mean, population standard deviation, and z-score calculations; they do
not call an LLM or ask one to recalculate values.

### Explanations

`OpenAIResponsesExplainer` uses the same `OPENAI_API_KEY` and
`VERIDOC_LLM_MODEL` configuration when an injected explanation service elects
to use it. It sends only serialized `VerificationFinding` values and disables
response storage. The model returns structured narrative drafts, never an
authoritative finding or numerical calculation. The application validates each
draft and deterministically falls back when it is unsafe, incomplete, invalid,
or unavailable. See [ADR 0004](decisions/0004-use-validated-llm-proposals-for-explanations.md).

The explanation graph has no standalone HTTP endpoint; `POST /process` delivers
its canonical explanations together with the extraction, findings, and verdict.

## Failure handling and data safety

Upload validation rejects malformed, encrypted/repaired, oversized, unsupported,
or type-mismatched documents before OCR. OCR unavailability maps to HTTP 503 and
processing failures map to HTTP 422. Extraction configuration/provider failures
map to `extraction_unavailable` (503); missing or invalid structured provider
output maps to `extraction_processing_failed` (422). Reference-data failures map
to `reference_data_unavailable` (503), and an incomplete orchestration result
maps to `processing_failed` (422). Public errors never expose paths, stack
traces, credentials, document bytes, raw OCR text, or provider responses.

Administration rejects missing or incorrect credentials uniformly, bounds JSON
imports before parsing, validates all records before beginning the write
transaction, and rolls the transaction back on rejected conflicts. Responses
contain reference facts and provenance only. Backup/restore failures use one
generic local maintenance error rather than exposing a filesystem path.

The current implementation does not log document bodies, OCR text, extracted
fields, rendered pages, credentials, verification findings, or temporary paths.
Extraction provider calls send only the current request's OCR text and
normalized page images. Explanation provider calls send canonical verification
findings only; neither provider adapter retains a response through the request
it makes.

## Operational observability

The FastAPI middleware assigns a safe request ID before route handling, returns
it as `X-Request-ID`, and emits one `veridoc.request` completion record. The
record includes the ID, method, path without query text, status code, and
duration only. The header may carry a bounded safe client correlation value, but
does not identify a document, reviewer, or approval decision. `GET /health` is
a liveness signal for the HTTP application, not a readiness probe for OCR,
provider, or SQLite dependencies.

## Current tradeoffs and limitations

- OCR text and images are combined to preserve layout context that plain text
  alone loses, at the cost of sending document data to the configured provider.
- The complete graph composes existing one-node stage graphs and adds no hidden
  workflow state or separate background queue.
- Pydantic structured parsing rejects malformed provider output instead of
  attempting an OCR-only or heuristic fallback.
- Phase 3 uses extracted vendor names or identifiers as normalized local lookup
  keys; it does not provide authoritative vendor identity resolution.
- Explanation-provider prose is deliberately constrained. Any invalid, unsafe,
  or unavailable provider output yields a deterministic result rather than an
  unsupported claim.
- The product behavior completed through Phase 6 has one synchronous processing
  endpoint and a stateless local review page. Phase 7 adds no runtime feature;
  Phase 8 adds local shared-token reference-data administration only. The
  service has no user accounts or roles, standalone verification or explanation
  endpoint, approval action, malware scanning, automated retention service,
  persistent audit trail, or review record. Its request ID is useful for
  operational correlation but does not replace those controls.
