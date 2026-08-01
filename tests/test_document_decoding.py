"""Tests for invoice document decoding."""

from io import BytesIO

import fitz
from PIL import Image

from veridoc.ingestion.decoding import decode_document
from veridoc.ingestion.models import UploadedDocument


def test_normalizes_png_invoice_to_single_png_page() -> None:
    """A valid image invoice is preserved as an OCR-ready page."""
    image_bytes = BytesIO()
    Image.new("RGB", (20, 10), color="white").save(image_bytes, format="PNG")
    document = UploadedDocument(
        filename="invoice.png",
        media_type="image/png",
        content=image_bytes.getvalue(),
    )

    pages = decode_document(document)

    assert len(pages) == 1
    assert pages[0].page_number == 1
    assert pages[0].image_bytes.startswith(b"\x89PNG\r\n\x1a\n")


def test_renders_pdf_invoice_to_png_page() -> None:
    """A PDF invoice is rendered into a PNG before OCR."""
    pdf = fitz.open()
    pdf.new_page().insert_text((72, 72), "Synthetic invoice")
    document = UploadedDocument(
        filename="invoice.pdf",
        media_type="application/pdf",
        content=pdf.tobytes(),
    )
    pdf.close()

    pages = decode_document(document)

    assert len(pages) == 1
    assert pages[0].image_bytes.startswith(b"\x89PNG\r\n\x1a\n")
