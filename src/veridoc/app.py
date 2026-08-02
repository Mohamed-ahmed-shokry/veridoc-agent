"""FastAPI application setup for Veridoc."""

import logging
import os
import re
import time
from typing import Annotated, Literal
from uuid import uuid4

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse, Response
from pydantic import BaseModel
from starlette.middleware.base import RequestResponseEndpoint

from veridoc import __version__
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
from veridoc.ingestion.validation import (
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


class HealthResponse(BaseModel):
    """Typed response returned by the service health check."""

    status: Literal["ok"]


app = FastAPI(
    title="Veridoc",
    description="Invoice and purchase-order verification service.",
    version=__version__,
)


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


def get_structured_extractor() -> StructuredExtractor:
    """Build the configured structured extraction adapter for one request."""
    settings = OpenAIExtractionSettings.from_environment()
    return OpenAIResponsesExtractor(settings)


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


def get_explanation_service() -> ExplanationService:
    """Build optional provider guidance with deterministic fallback when unset."""
    try:
        settings = OpenAIExplanationSettings.from_environment()
    except ExplanationUnavailableError:
        return ExplanationService()
    return ExplanationService(OpenAIResponsesExplainer(settings))


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
    file: Annotated[UploadFile, File(description="A PDF, PNG, or JPEG invoice.")],
    engine: Annotated[OCREngine, Depends(get_ocr_engine)],
) -> OCRResponse:
    """Validate one invoice upload and return raw OCR text and confidence."""
    try:
        data = await read_bounded_upload(file)
        upload = validate_upload(
            data,
            filename=file.filename,
            declared_content_type=file.content_type,
        )
        result = OCRService(engine).process(upload)
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
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
    finally:
        await file.close()

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
    file: Annotated[UploadFile, File(description="A PDF, PNG, or JPEG invoice.")],
    ocr_engine: Annotated[OCREngine, Depends(get_ocr_engine)],
    extractor: Annotated[StructuredExtractor, Depends(get_structured_extractor)],
) -> InvoiceExtraction:
    """Validate one upload and return typed evidence-linked extraction data."""
    try:
        data = await read_bounded_upload(file)
        upload = validate_upload(
            data,
            filename=file.filename,
            declared_content_type=file.content_type,
        )
        return await ExtractionService(ocr_engine, extractor).process(upload)
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
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
    finally:
        await file.close()


@app.post("/process", response_model=ProcessingResult, tags=["processing"])
async def process_invoice(
    file: Annotated[UploadFile, File(description="A PDF, PNG, or JPEG invoice.")],
    service: Annotated[ProcessingService, Depends(get_processing_service)],
) -> ProcessingResult:
    """Return extraction, findings, explanations, and a deterministic verdict."""
    try:
        data = await read_bounded_upload(file)
        upload = validate_upload(
            data,
            filename=file.filename,
            declared_content_type=file.content_type,
        )
        return await service.process(upload)
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
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
    finally:
        await file.close()
