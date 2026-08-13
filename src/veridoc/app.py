"""FastAPI application setup for Veridoc."""

import logging
import os
import re
import time
from asyncio import to_thread
from collections.abc import AsyncIterator
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.exceptions import RequestValidationError
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.middleware.base import RequestResponseEndpoint
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from veridoc import __version__
from veridoc.administration.api import router as administration_router
from veridoc.administration.models import MAX_ADMIN_IMPORT_BYTES
from veridoc.explanation.config import OpenAIExplanationSettings
from veridoc.explanation.openai_responses import OpenAIResponsesExplainer
from veridoc.explanation.protocol import ExplanationUnavailableError
from veridoc.explanation.service import ExplanationService
from veridoc.extraction.config import OpenAIExtractionSettings
from veridoc.extraction.models import InvoiceExtraction
from veridoc.extraction.openai_responses import OpenAIResponsesExtractor
from veridoc.extraction.protocol import (
    ExtractionProcessingError,
    ExtractionUnavailableError,
    StructuredExtractor,
)
from veridoc.extraction.service import ExtractionService
from veridoc.ingestion.models import ValidatedUpload
from veridoc.ingestion.validation import (
    MAX_UPLOAD_BYTES,
    UploadValidationError,
    read_bounded_upload,
    validate_upload,
)
from veridoc.ocr.models import OCRPage, OCRResponse
from veridoc.ocr.protocol import OCREngine, OCRProcessingError, OCRUnavailableError
from veridoc.ocr.service import OCRService
from veridoc.ocr.tesseract import TesseractEngine
from veridoc.persistence.protocol import (
    InvoiceRepository,
    ReferenceDataUnavailableError,
)
from veridoc.persistence.sqlite import SQLiteInvoiceRepository
from veridoc.processing.models import ProcessingResult
from veridoc.processing.service import ProcessingError, ProcessingService
from veridoc.review.page import render_review_page
from veridoc.verification.service import VerificationService

_REQUEST_LOGGER = logging.getLogger("veridoc.request")
_REQUEST_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,127}$")
_MULTIPART_OVERHEAD_BYTES = 64 * 1024
MAX_DOCUMENT_REQUEST_BYTES = MAX_UPLOAD_BYTES + _MULTIPART_OVERHEAD_BYTES
MAX_ADMIN_IMPORT_REQUEST_BYTES = MAX_ADMIN_IMPORT_BYTES + _MULTIPART_OVERHEAD_BYTES
MAX_ADMIN_JSON_REQUEST_BYTES = MAX_ADMIN_IMPORT_BYTES
_ADMIN_JSON_PATH_PATTERN = re.compile(
    r"^/admin/reference-data/(?:invoices|purchase-orders)(?:/[^/]+)?$"
)


class HealthResponse(BaseModel):
    """Typed response returned by the service health check."""

    status: Literal["ok"]


class RequestBodyLimitMiddleware:
    """Reject oversized multipart requests before body parsing or spooling."""

    def __init__(self, app: ASGIApp) -> None:
        self._app = app

    async def __call__(
        self,
        scope: Scope,
        receive: Receive,
        send: Send,
    ) -> None:
        if scope["type"] != "http":
            await self._app(scope, receive, send)
            return

        limit = _request_body_limit(
            _route_relative_path(scope), str(scope.get("method", ""))
        )
        if limit is None:
            await self._app(scope, receive, send)
            return

        maximum_bytes, code, message = limit
        content_length = _content_length(scope)
        if content_length is not None and content_length > maximum_bytes:
            await _send_body_too_large(scope, receive, send, code, message)
            return

        body = bytearray()
        received_request = False
        disconnected = False
        while True:
            incoming = await receive()
            if incoming["type"] == "http.disconnect":
                disconnected = True
                break
            if incoming["type"] != "http.request":
                continue
            received_request = True
            body.extend(incoming.get("body", b""))
            if len(body) > maximum_bytes:
                await _send_body_too_large(scope, receive, send, code, message)
                return
            if not incoming.get("more_body", False):
                break

        replay_body = bytes(body)
        replayed = False

        async def replay_receive() -> Message:
            nonlocal replayed
            if received_request and not replayed:
                replayed = True
                return {
                    "type": "http.request",
                    "body": replay_body,
                    "more_body": disconnected,
                }
            return {"type": "http.disconnect"}

        await self._app(scope, replay_receive, send)


def _request_body_limit(path: str, method: str) -> tuple[int, str, str] | None:
    if path in {"/ocr", "/extract", "/process"}:
        return (
            MAX_DOCUMENT_REQUEST_BYTES,
            "upload_too_large",
            f"Uploads must not exceed {MAX_UPLOAD_BYTES} bytes.",
        )
    if path == "/admin/reference-data/import":
        return (
            MAX_ADMIN_IMPORT_REQUEST_BYTES,
            "reference_data_import_too_large",
            "The reference-data import exceeds the size limit.",
        )
    if method.upper() in {"POST", "PUT"} and _ADMIN_JSON_PATH_PATTERN.fullmatch(path):
        return (
            MAX_ADMIN_JSON_REQUEST_BYTES,
            "reference_data_request_too_large",
            "The reference-data request exceeds the size limit.",
        )
    return None


def _route_relative_path(scope: Scope) -> str:
    path = str(scope.get("path", ""))
    root_path = str(scope.get("root_path", "")).rstrip("/")
    if root_path and path.startswith(f"{root_path}/"):
        path = path[len(root_path) :]
    return path.rstrip("/") or "/"


def _content_length(scope: Scope) -> int | None:
    for name, value in scope.get("headers", []):
        if name.lower() != b"content-length":
            continue
        try:
            parsed = int(value)
        except ValueError:
            return None
        return parsed if parsed >= 0 else None
    return None


async def _send_body_too_large(
    scope: Scope,
    receive: Receive,
    send: Send,
    code: str,
    message: str,
) -> None:
    response = JSONResponse(
        status_code=413,
        content={"detail": {"code": code, "message": message}},
    )
    await response(scope, receive, send)


app = FastAPI(
    title="Veridoc",
    description="Invoice and purchase-order verification service.",
    version=__version__,
)
app.include_router(administration_router)
app.add_middleware(RequestBodyLimitMiddleware)


@app.middleware("http")
async def add_request_context(
    request: Request, call_next: RequestResponseEndpoint
) -> Response:
    """Attach a safe request identifier and log one metadata-only completion line."""
    request_id = _request_id(request.headers.get("X-Request-ID"))
    request.state.request_id = request_id
    started_at = time.perf_counter()
    status_code = 500
    try:
        response = await call_next(request)
        status_code = response.status_code
        response.headers["X-Request-ID"] = request_id
        return response
    finally:
        _REQUEST_LOGGER.info(
            "request_complete request_id=%s method=%s path=%s status_code=%s duration_ms=%.1f",
            request_id,
            request.method,
            request.url.path,
            status_code,
            (time.perf_counter() - started_at) * 1000,
        )


def _request_id(supplied_value: str | None) -> str:
    """Return a bounded safe client correlation value or a generated identifier."""
    if supplied_value and _REQUEST_ID_PATTERN.fullmatch(supplied_value):
        return supplied_value
    return uuid4().hex


@app.exception_handler(RequestValidationError)
async def handle_request_validation_error(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """Return a safe request-validation error without echoing submitted data."""
    del request, exc
    return JSONResponse(
        status_code=422,
        content={
            "detail": {
                "code": "invalid_request",
                "message": "The request is invalid.",
            }
        },
    )


@app.exception_handler(ExtractionUnavailableError)
async def handle_extraction_unavailable(
    request: Request, exc: ExtractionUnavailableError
) -> JSONResponse:
    """Return a safe provider-availability error for structured extraction."""
    del request
    return JSONResponse(
        status_code=503,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(OCRUnavailableError)
async def handle_ocr_unavailable(
    request: Request, exc: OCRUnavailableError
) -> JSONResponse:
    """Return a safe OCR-availability error during dependency construction."""
    del request
    return JSONResponse(
        status_code=503,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(ExtractionProcessingError)
async def handle_extraction_processing_error(
    request: Request, exc: ExtractionProcessingError
) -> JSONResponse:
    """Return a safe invalid-extraction error without exposing provider output."""
    del request
    return JSONResponse(
        status_code=422,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(ReferenceDataUnavailableError)
async def handle_reference_data_unavailable(
    request: Request, exc: ReferenceDataUnavailableError
) -> JSONResponse:
    """Return a safe reference-data availability error for complete processing."""
    del request
    return JSONResponse(
        status_code=503,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(ProcessingError)
async def handle_processing_error(
    request: Request, exc: ProcessingError
) -> JSONResponse:
    """Return a safe failure when orchestration lacks a typed result."""
    del request
    return JSONResponse(
        status_code=422,
        content={"detail": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(Exception)
async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
    """Return a safe correlated response for an unexpected application failure."""
    del exc
    request_id = _request_id(getattr(request.state, "request_id", None))
    return JSONResponse(
        status_code=500,
        content={
            "detail": {
                "code": "internal_server_error",
                "message": "An unexpected server error occurred.",
            }
        },
        headers={"X-Request-ID": request_id},
    )


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    """Return the service health status without touching external dependencies."""
    return HealthResponse(status="ok")


@app.get("/review", response_class=HTMLResponse, include_in_schema=False)
def review_page() -> HTMLResponse:
    """Serve the intentionally small local invoice-review interface."""
    return HTMLResponse(render_review_page())


def get_ocr_engine() -> OCREngine:
    """Build the configured OCR engine for one request."""
    return TesseractEngine()


async def get_validated_upload(
    file: Annotated[UploadFile, File(description="A PDF, PNG, or JPEG invoice.")],
) -> ValidatedUpload:
    """Read, validate, and close one upload before external dependencies resolve."""
    try:
        data = await read_bounded_upload(file)
        return await to_thread(
            validate_upload,
            data,
            filename=file.filename,
            declared_content_type=file.content_type,
        )
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    finally:
        await file.close()


async def get_structured_extractor() -> AsyncIterator[StructuredExtractor]:
    """Yield one configured extraction adapter and close its provider client."""
    settings = OpenAIExtractionSettings.from_environment()
    extractor = OpenAIResponsesExtractor(settings)
    try:
        yield extractor
    finally:
        await extractor.aclose()


def get_invoice_repository() -> InvoiceRepository:
    """Open and initialize the configured local reference-data repository."""
    database_path = os.environ.get(
        "VERIDOC_REFERENCE_DATABASE", "veridoc-reference.sqlite3"
    ).strip()
    repository = SQLiteInvoiceRepository(database_path or "veridoc-reference.sqlite3")
    repository.initialize()
    return repository


def get_verification_service(
    repository: Annotated[InvoiceRepository, Depends(get_invoice_repository)],
) -> VerificationService:
    """Build the deterministic verification service for one processing request."""
    return VerificationService(repository)


async def get_explanation_service() -> AsyncIterator[ExplanationService]:
    """Yield optional provider guidance and close any configured client."""
    try:
        settings = OpenAIExplanationSettings.from_environment()
    except ExplanationUnavailableError:
        yield ExplanationService()
        return

    explainer = OpenAIResponsesExplainer(settings)
    try:
        yield ExplanationService(explainer)
    finally:
        await explainer.aclose()


def get_processing_service(
    ocr_engine: Annotated[OCREngine, Depends(get_ocr_engine)],
    extractor: Annotated[StructuredExtractor, Depends(get_structured_extractor)],
    verification_service: Annotated[
        VerificationService, Depends(get_verification_service)
    ],
    explanation_service: Annotated[
        ExplanationService, Depends(get_explanation_service)
    ],
) -> ProcessingService:
    """Compose the complete typed processing graph for one API request."""
    return ProcessingService(
        ocr_engine,
        extractor,
        verification_service,
        explanation_service,
    )


@app.post("/ocr", response_model=OCRResponse, tags=["ocr"])
async def run_ocr(
    upload: Annotated[ValidatedUpload, Depends(get_validated_upload)],
    engine: Annotated[OCREngine, Depends(get_ocr_engine)],
) -> OCRResponse:
    """Validate one invoice upload and return raw OCR text and confidence."""
    try:
        result = await to_thread(OCRService(engine).process, upload)
    except OCRUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except OCRProcessingError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    return OCRResponse(
        media_type=result.media_type,
        text=result.text,
        confidence=result.confidence,
        pages=[
            OCRPage(page_number=index, text=page.text, confidence=page.confidence)
            for index, page in enumerate(result.pages, start=1)
        ],
    )


@app.post("/extract", response_model=InvoiceExtraction, tags=["extraction"])
async def extract_invoice(
    upload: Annotated[ValidatedUpload, Depends(get_validated_upload)],
    ocr_engine: Annotated[OCREngine, Depends(get_ocr_engine)],
    extractor: Annotated[StructuredExtractor, Depends(get_structured_extractor)],
) -> InvoiceExtraction:
    """Validate one upload and return typed evidence-linked extraction data."""
    try:
        return await ExtractionService(ocr_engine, extractor).process(upload)
    except OCRUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except OCRProcessingError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": exc.message},
        ) from exc


@app.post("/process", response_model=ProcessingResult, tags=["processing"])
async def process_invoice(
    upload: Annotated[ValidatedUpload, Depends(get_validated_upload)],
    service: Annotated[ProcessingService, Depends(get_processing_service)],
) -> ProcessingResult:
    """Return extraction, findings, explanations, and a deterministic verdict."""
    try:
        return await service.process(upload)
    except OCRUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except OCRProcessingError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
