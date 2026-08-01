"""OCR response contract tests."""

import pytest
from pydantic import ValidationError

from veridoc.ocr.models import OCRDocumentResult, OCRPage, OCRPageResult, OCRResponse


def test_document_result_joins_pages_and_averages_confidence() -> None:
    result = OCRDocumentResult(
        media_type="application/pdf",
        pages=(
            OCRPageResult(text="first", confidence=80.0),
            OCRPageResult(text="second", confidence=None),
            OCRPageResult(text="third", confidence=90.0),
        ),
    )

    assert result.text == "first\fsecond\fthird"
    assert result.confidence == 85.0


def test_response_requires_a_valid_page_number_and_confidence_range() -> None:
    response = OCRResponse(
        media_type="image/png",
        text="Invoice INV-001",
        pages=[OCRPage(page_number=1, text="Invoice INV-001", confidence=92.5)],
    )

    assert response.pages[0].page_number == 1

    with pytest.raises(ValidationError):
        OCRPage(page_number=0, text="bad")
    with pytest.raises(ValidationError):
        OCRPage(page_number=1, text="bad", confidence=101)
