"""FastAPI application setup for Veridoc."""

from typing import Annotated, Literal

from fastapi import Depends, FastAPI, File, HTTPException, Request, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from veridoc import __version__
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


class HealthResponse(BaseModel):
    """Typed response returned by the service health check."""

    status: Literal["ok"]


app = FastAPI(
    title="Veridoc",
    description="Invoice and purchase-order verification service.",
    version=__version__,
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


@app.get("/health", response_model=HealthResponse, tags=["system"])
def health_check() -> HealthResponse:
    """Return the service health status without touching external dependencies."""
    return HealthResponse(status="ok")


def get_ocr_engine() -> OCREngine:
    """Build the configured OCR engine for one request."""
    return TesseractEngine()


def get_structured_extractor() -> StructuredExtractor:
    """Build the configured structured extraction adapter for one request."""
    settings = OpenAIExtractionSettings.from_environment()
    return OpenAIResponsesExtractor(settings)


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
