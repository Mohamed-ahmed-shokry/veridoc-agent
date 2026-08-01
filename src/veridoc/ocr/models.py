"""Typed results returned by OCR implementations."""

from pydantic import BaseModel, ConfigDict, Field


class OcrPageResult(BaseModel):
    """OCR text and confidence data for one document page."""

    model_config = ConfigDict(frozen=True)

    page_number: int = Field(ge=1)
    text: str
    mean_confidence: float | None = Field(default=None, ge=0, le=1)


class OcrResult(BaseModel):
    """OCR output for an uploaded invoice document."""

    model_config = ConfigDict(frozen=True)

    text: str
    pages: tuple[OcrPageResult, ...]
    mean_confidence: float | None = Field(default=None, ge=0, le=1)
