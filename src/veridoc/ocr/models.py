"""Typed values exchanged by OCR adapters and the HTTP boundary."""

from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from veridoc.ingestion.models import DocumentMediaType


@dataclass(frozen=True, slots=True)
class OCRPageResult:
    """Text and optional aggregate confidence for one decoded page."""

    text: str
    confidence: float | None


@dataclass(frozen=True, slots=True)
class OCRDocumentResult:
    """OCR output for one validated upload."""

    media_type: DocumentMediaType
    pages: tuple[OCRPageResult, ...]

    @property
    def text(self) -> str:
        """Return page text separated by a stable form-feed boundary."""
        return "\f".join(page.text for page in self.pages)

    @property
    def confidence(self) -> float | None:
        """Return the mean confidence of pages that reported confidence."""
        values = [page.confidence for page in self.pages if page.confidence is not None]
        return sum(values) / len(values) if values else None


@dataclass(frozen=True, slots=True)
class RenderedPage:
    """One normalized raster page retained for a downstream vision boundary."""

    page_number: int
    image_bytes: bytes


@dataclass(frozen=True, slots=True)
class OCRDocumentBundle:
    """OCR results paired with normalized in-memory page images."""

    document: OCRDocumentResult
    page_images: tuple[RenderedPage, ...]


class OCRPage(BaseModel):
    """Public OCR response details for one page."""

    page_number: int = Field(ge=1)
    text: str
    confidence: float | None = Field(default=None, ge=0, le=100)


class OCRResponse(BaseModel):
    """Public raw OCR response returned by the Phase 1 endpoint."""

    media_type: Literal["application/pdf", "image/jpeg", "image/png"]
    text: str
    confidence: float | None = Field(default=None, ge=0, le=100)
    pages: list[OCRPage]
