"""Programmatically generated fictional invoice documents."""

from __future__ import annotations

from io import BytesIO

import fitz
from PIL import Image, ImageDraw


def fictional_invoice_png() -> bytes:
    """Return a deterministic fictional invoice image with no real data."""
    image = Image.new("RGB", (640, 360), color="white")
    draw = ImageDraw.Draw(image)
    lines = (
        "Fictional Northwind Supplies",
        "Invoice INV-0001",
        "Purchase Order PO-0042",
        "Subtotal 120.00 USD   Tax 12.00 USD   Total 132.00 USD",
    )
    for index, line in enumerate(lines):
        draw.text((24, 24 + index * 48), line, fill="black")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def fictional_invoice_pdf(page_count: int = 1) -> bytes:
    """Return deterministic PDF pages containing fictional invoice text."""
    if page_count < 1:
        raise ValueError("page_count must be positive")
    document = fitz.open()
    for index in range(page_count):
        page = document.new_page(width=300, height=180)
        page.insert_text((20, 40), "Fictional Northwind Supplies")
        page.insert_text((20, 70), f"Invoice INV-{index + 1:04d}")
        page.insert_text((20, 100), "Purchase Order PO-0042")
        page.insert_text((20, 130), "Total 132.00 USD")
    document.set_metadata(
        {
            "format": "PDF 1.7",
            "title": "Fictional Invoice Fixture",
            "author": "Veridoc Tests",
            "subject": "Synthetic invoice",
            "keywords": "fictional,invoice",
            "creator": "Veridoc Tests",
            "producer": "Veridoc Tests",
            "creationDate": "D:20200101000000",
            "modDate": "D:20200101000000",
        }
    )
    data = document.tobytes(
        garbage=4,
        deflate=True,
        clean=True,
        no_new_id=True,
    )
    document.close()
    return data
