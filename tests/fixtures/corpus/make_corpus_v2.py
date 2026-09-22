"""Deterministic construction for the benchmark corpus v2 documents.

Builds the 17 Phase 13 documents (doc-004 through doc-020) plus their
ground-truth files, then prints the manifest entries with SHA-256 digests.
Run from the repository root::

    uv run python tests/fixtures/corpus/make_corpus_v2.py

Construction follows ADR 0024: Latin lines use the Pillow default bitmap
font, Arabic content is pixel-spliced from the verified doc_003 rendering,
noisy variants use fixed Pillow transforms, and multi-page PDFs embed
composed page images or deterministic PyMuPDF text pages. The committed
bytes are the corpus; this script exists so construction stays auditable.
Tests and the benchmark consume only the committed files and need no fonts.
"""

from __future__ import annotations

import hashlib
import json
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter

CORPUS_DIR = Path(__file__).resolve().parent
INVOICES_DIR = CORPUS_DIR / "invoices"
GROUND_TRUTH_DIR = CORPUS_DIR / "ground_truth"
ARABIC_VENDOR = "شركة الأمل للتوريدات"

_PDF_METADATA = {
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


def _latin_lines(
    vendor: str,
    number: str,
    purchase_order: str,
    issued: str,
    items: list[str],
    amounts: list[str],
) -> list[str]:
    return [
        vendor,
        f"Invoice {number}",
        f"Purchase Order {purchase_order}",
        f"Date {issued}",
        *items,
        *amounts,
    ]


def _clean_png(lines: list[str], *, y_step: int = 44) -> bytes:
    image = Image.new("RGB", (640, 360), color="white")
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(lines):
        draw.text((24, 24 + index * y_step), line, fill="black")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _arabic_band() -> Image.Image:
    source = Image.open(CORPUS_DIR / "invoices" / "doc_003.png").convert("RGB")
    return source.crop((0, 0, 640, 60))


def _arabic_png(
    latin_lines: list[str], *, dense_side: list[str] | None = None
) -> bytes:
    image = Image.new("RGB", (640, 360), color="white")
    image.paste(_arabic_band(), (0, 0))
    draw = ImageDraw.Draw(image)
    for index, line in enumerate(latin_lines):
        draw.text((24, 72 + index * 44), line, fill="black")
    if dense_side is not None:
        for index, line in enumerate(dense_side):
            width = draw.textlength(line)
            draw.text((616 - width, 72 + index * 44), line, fill="black")
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _noisy(data: bytes) -> bytes:
    image = Image.open(BytesIO(data)).convert("RGB")
    image = image.rotate(1.2, resample=Image.BICUBIC, expand=True, fillcolor="white")
    image = ImageEnhance.Contrast(image).enhance(0.85)
    image = image.filter(ImageFilter.GaussianBlur(0.4))
    output = BytesIO()
    image.save(output, format="PNG")
    return output.getvalue()


def _text_pdf(pages: list[list[str]]) -> bytes:
    document = pymupdf.open()
    for lines in pages:
        page = document.new_page(width=595, height=842)
        for index, line in enumerate(lines):
            page.insert_text((56, 72 + index * 28), line)
    document.set_metadata(_PDF_METADATA)
    data = document.tobytes(garbage=4, deflate=True, clean=True, no_new_id=True)
    document.close()
    return data


def _image_pdf(pages: list[bytes]) -> bytes:
    document = pymupdf.open()
    for png in pages:
        image = Image.open(BytesIO(png))
        width, height = image.size
        page = document.new_page(width=width, height=height)
        page.insert_image(pymupdf.Rect(0, 0, width, height), stream=png)
    document.set_metadata(_PDF_METADATA)
    data = document.tobytes(garbage=4, deflate=True, clean=True, no_new_id=True)
    document.close()
    return data


def _ground_truth(
    *,
    number: str,
    issued: str,
    vendor: str,
    currency: str,
    total: str,
    subtotal: str | None,
    tax: str | None,
    items: list[tuple[str, str, str, str]],
    findings: list[str],
    verdict: str,
    transcript: str,
) -> dict:
    issued_date = date.fromisoformat(issued)
    return {
        "invoice_number": number,
        "invoice_date": issued,
        "due_date": (
            (issued_date + timedelta(days=30)).isoformat() if subtotal else None
        ),
        "vendor_name": vendor,
        "vendor_tax_id": None,
        "currency": currency,
        "total_amount": total,
        "subtotal_amount": subtotal,
        "tax_amount": tax,
        "line_items": [
            {
                "description": description,
                "quantity": quantity,
                "unit_price": unit_price,
                "total_amount": line_total,
            }
            for description, quantity, unit_price, line_total in items
        ],
        "expected_finding_types": findings,
        "expected_verdict": verdict,
        "ocr_transcript": transcript,
    }


def _specs() -> list[dict]:
    specs = [
        # --- eng / clean / standard singles (PNG) ---
        {
            "id": "doc-004",
            "kind": "png",
            "slice": ("eng", "clean", "standard"),
            "vendor": "Northwind Traders",
            "number": "INV-2026-0004",
            "purchase_order": "PO-2026-04",
            "issued": "2026-03-02",
            "items": [("Office Chairs", "2", "150.00", "300.00")],
            "item_lines": ["2 x Office Chairs @ 150.00 = 300.00"],
            "subtotal": "300.00",
            "tax": "30.00",
            "total": "330.00",
            "currency": "USD",
            "findings": [],
            "verdict": "clear",
        },
        {
            "id": "doc-005",
            "kind": "png",
            "slice": ("eng", "clean", "standard"),
            "vendor": "Contoso Manufacturing",
            "number": "INV-2026-0005",
            "purchase_order": "PO-2026-05",
            "issued": "2026-03-03",
            "items": [
                ("Steel Beams", "10", "40.00", "400.00"),
                ("Bolts Pack", "4", "25.00", "100.00"),
            ],
            "item_lines": [
                "10 x Steel Beams @ 40.00 = 400.00",
                "4 x Bolts Pack @ 25.00 = 100.00",
            ],
            "subtotal": "500.00",
            "tax": "50.00",
            "total": "550.00",
            "currency": "USD",
            "findings": [],
            "verdict": "clear",
        },
        {
            "id": "doc-006",
            "kind": "png",
            "slice": ("eng", "clean", "standard"),
            "vendor": "Fabrikam Wholesale",
            "number": "INV-2026-0006",
            "purchase_order": "PO-2026-06",
            "issued": "2026-03-04",
            "items": [("Paper Reams", "20", "10.00", "200.00")],
            "item_lines": ["20 x Paper Reams @ 10.00 = 200.00"],
            "subtotal": "200.00",
            "tax": "20.00",
            "total": "230.00",
            "currency": "USD",
            "findings": ["invoice_total_mismatch"],
            "verdict": "review_required",
        },
        {
            "id": "doc-007",
            "kind": "png",
            "slice": ("eng", "clean", "standard"),
            "vendor": "Adventure Works Supply",
            "number": "INV-2026-0007",
            "purchase_order": "PO-2026-07",
            "issued": "2026-03-05",
            "items": [],
            "item_lines": [],
            "subtotal": None,
            "tax": None,
            "total": "99.99",
            "currency": "USD",
            "findings": [],
            "verdict": "clear",
        },
        # --- eng / clean / standard multis (PDF text pages) ---
        {
            "id": "doc-008",
            "kind": "pdf-text",
            "slice": ("eng", "clean", "standard"),
            "vendor": "Blue Yonder Freight",
            "number": "INV-2026-0008",
            "purchase_order": "PO-2026-08",
            "issued": "2026-03-06",
            "items": [("Freight Lanes", "3", "220.00", "660.00")],
            "item_lines": ["3 x Freight Lanes @ 220.00 = 660.00"],
            "subtotal": "660.00",
            "tax": "66.00",
            "total": "726.00",
            "currency": "USD",
            "findings": [],
            "verdict": "clear",
        },
        {
            "id": "doc-009",
            "kind": "pdf-text",
            "slice": ("eng", "clean", "standard"),
            "vendor": "Crescent Foods Ltd",
            "number": "INV-2026-0009",
            "purchase_order": "PO-2026-09",
            "issued": "2026-03-07",
            "items": [("Olive Oil Cases", "12", "35.00", "420.00")],
            "item_lines": ["12 x Olive Oil Cases @ 35.00 = 420.00"],
            "subtotal": "420.00",
            "tax": "42.00",
            "total": "462.00",
            "currency": "USD",
            "findings": [],
            "verdict": "clear",
        },
        {
            "id": "doc-010",
            "kind": "pdf-text",
            "slice": ("eng", "clean", "standard"),
            "vendor": "Globex Corporation",
            "number": "INV-2026-0010",
            "purchase_order": "PO-2026-10",
            "issued": "2026-03-08",
            "items": [("Server Racks", "5", "200.00", "1000.00")],
            "item_lines": ["5 x Server Racks @ 200.00 = 1000.00"],
            "subtotal": "1000.00",
            "tax": "100.00",
            "total": "1150.00",
            "currency": "USD",
            "findings": ["invoice_total_mismatch"],
            "verdict": "review_required",
        },
        {
            "id": "doc-011",
            "kind": "pdf-text",
            "slice": ("eng", "clean", "standard"),
            "vendor": "Hooli Systems",
            "number": "INV-2026-0011",
            "purchase_order": "PO-2026-11",
            "issued": "2026-03-09",
            "items": [],
            "item_lines": [],
            "subtotal": None,
            "tax": None,
            "total": "75.50",
            "currency": "USD",
            "findings": [],
            "verdict": "clear",
        },
        # --- ara / noisy / dense singles (spliced PNG + noise) ---
        {
            "id": "doc-012",
            "kind": "png-ar",
            "slice": ("ara", "noisy", "dense"),
            "vendor": ARABIC_VENDOR,
            "number": "INV-2026-0012",
            "purchase_order": "PO-2026-12",
            "issued": "2026-04-01",
            "items": [],
            "item_lines": [],
            "subtotal": None,
            "tax": None,
            "total": "320.00",
            "currency": "EGP",
            "findings": [],
            "verdict": "clear",
        },
        {
            "id": "doc-013",
            "kind": "png-ar",
            "slice": ("ara", "noisy", "dense"),
            "vendor": ARABIC_VENDOR,
            "number": "INV-2026-0013",
            "purchase_order": "PO-2026-13",
            "issued": "2026-04-02",
            "items": [("Office Supplies", "5", "80.00", "400.00")],
            "item_lines": ["5 x Office Supplies @ 80.00 = 400.00"],
            "subtotal": "400.00",
            "tax": "40.00",
            "total": "440.00",
            "currency": "EGP",
            "findings": [],
            "verdict": "clear",
        },
        {
            "id": "doc-014",
            "kind": "png-ar",
            "slice": ("ara", "noisy", "dense"),
            "vendor": ARABIC_VENDOR,
            "number": "INV-2026-0014",
            "purchase_order": "PO-2026-14",
            "issued": "2026-04-03",
            "items": [("Spare Parts", "3", "50.00", "150.00")],
            "item_lines": ["3 x Spare Parts @ 50.00 = 150.00"],
            "subtotal": "150.00",
            "tax": "15.00",
            "total": "175.00",
            "currency": "EGP",
            "findings": ["invoice_total_mismatch"],
            "verdict": "review_required",
        },
        {
            "id": "doc-015",
            "kind": "png-ar",
            "slice": ("ara", "noisy", "dense"),
            "vendor": ARABIC_VENDOR,
            "number": "INV-2026-0015",
            "purchase_order": "PO-2026-15",
            "issued": "2026-04-04",
            "items": [],
            "item_lines": [],
            "subtotal": None,
            "tax": None,
            "total": "89.50",
            "currency": "EGP",
            "findings": [],
            "verdict": "clear",
            "dense": True,
        },
        # --- ara / noisy / dense multis (embedded PNG pages) ---
        {
            "id": "doc-016",
            "kind": "pdf-ar",
            "slice": ("ara", "noisy", "dense"),
            "vendor": ARABIC_VENDOR,
            "number": "INV-2026-0016",
            "purchase_order": "PO-2026-16",
            "issued": "2026-04-05",
            "items": [],
            "item_lines": [],
            "subtotal": None,
            "tax": None,
            "total": "610.00",
            "currency": "EGP",
            "findings": [],
            "verdict": "clear",
        },
        {
            "id": "doc-017",
            "kind": "pdf-ar",
            "slice": ("ara", "noisy", "dense"),
            "vendor": ARABIC_VENDOR,
            "number": "INV-2026-0017",
            "purchase_order": "PO-2026-17",
            "issued": "2026-04-06",
            "items": [("Cargo Freight", "2", "210.00", "420.00")],
            "item_lines": ["2 x Cargo Freight @ 210.00 = 420.00"],
            "subtotal": "420.00",
            "tax": "42.00",
            "total": "462.00",
            "currency": "EGP",
            "findings": [],
            "verdict": "clear",
        },
        {
            "id": "doc-018",
            "kind": "pdf-ar",
            "slice": ("ara", "noisy", "dense"),
            "vendor": ARABIC_VENDOR,
            "number": "INV-2026-0018",
            "purchase_order": "PO-2026-18",
            "issued": "2026-04-07",
            "items": [],
            "item_lines": [],
            "subtotal": None,
            "tax": None,
            "total": "145.25",
            "currency": "EGP",
            "findings": [],
            "verdict": "clear",
        },
        {
            "id": "doc-019",
            "kind": "pdf-ar",
            "slice": ("ara", "noisy", "dense"),
            "vendor": ARABIC_VENDOR,
            "number": "INV-2026-0019",
            "purchase_order": "PO-2026-19",
            "issued": "2026-04-08",
            "items": [("Packing Material", "8", "22.50", "180.00")],
            "item_lines": ["8 x Packing Material @ 22.50 = 180.00"],
            "subtotal": "180.00",
            "tax": "18.00",
            "total": "198.00",
            "currency": "EGP",
            "findings": [],
            "verdict": "clear",
        },
        {
            "id": "doc-020",
            "kind": "pdf-ar",
            "slice": ("ara", "noisy", "dense"),
            "vendor": ARABIC_VENDOR,
            "number": "INV-2026-0020",
            "purchase_order": "PO-2026-20",
            "issued": "2026-04-09",
            "items": [("Maintenance Tools", "6", "45.00", "270.00")],
            "item_lines": ["6 x Maintenance Tools @ 45.00 = 270.00"],
            "subtotal": "270.00",
            "tax": "27.00",
            "total": "310.00",
            "currency": "EGP",
            "findings": ["invoice_total_mismatch"],
            "verdict": "review_required",
        },
    ]
    return specs


def _amount_lines(spec: dict) -> list[str]:
    currency = spec["currency"]
    if spec["subtotal"] is None:
        return [f"Total {spec['total']} {currency}"]
    return [
        f"Subtotal {spec['subtotal']} {currency}   "
        f"Tax {spec['tax']} {currency}   "
        f"Total {spec['total']} {currency}"
    ]


def _pages(spec: dict) -> list[list[str]]:
    """Return the rendered line lists per page, in order, for one spec."""
    kind = spec["kind"]
    latin = _latin_lines(
        spec["vendor"] if kind in ("png", "pdf-text") else "",
        spec["number"],
        spec["purchase_order"],
        spec["issued"],
        spec["item_lines"],
        _amount_lines(spec),
    )
    latin = [line for line in latin if line]
    continued = [
        f"Continued {spec['number']}",
        f"Balance due {spec['total']} {spec['currency']}",
    ]
    if kind == "png":
        return [latin]
    if kind == "png-ar":
        return [[ARABIC_VENDOR, *latin]]
    if kind == "pdf-text":
        return [latin, continued]
    return [[ARABIC_VENDOR, *latin], [ARABIC_VENDOR, *continued]]


def _build(spec: dict) -> tuple[bytes, str, str, int]:
    kind = spec["kind"]
    pages = _pages(spec)
    if kind == "png":
        data = _clean_png(pages[0])
        return data, "image/png", ".png", 1
    if kind == "png-ar":
        dense_side = None
        if spec.get("dense"):
            dense_side = [
                spec["purchase_order"],
                spec["issued"],
                f"{spec['currency']} {spec['total']}",
            ]
        data = _noisy(_arabic_png(pages[0][1:], dense_side=dense_side))
        return data, "image/png", ".png", 1
    if kind == "pdf-text":
        return _text_pdf(pages), "application/pdf", ".pdf", 2
    page_images = [_noisy(_arabic_png(page[1:])) for page in pages]
    return _image_pdf(page_images), "application/pdf", ".pdf", 2


def main() -> None:
    INVOICES_DIR.mkdir(parents=True, exist_ok=True)
    GROUND_TRUTH_DIR.mkdir(parents=True, exist_ok=True)
    entries = []
    for spec in _specs():
        data, mime_type, suffix, page_count = _build(spec)
        number = spec["id"].replace("doc-", "doc_")
        invoice_path = INVOICES_DIR / f"{number}{suffix}"
        invoice_path.write_bytes(data)
        transcript = "\n".join(line for page in _pages(spec) for line in page)
        ground_truth = _ground_truth(
            number=spec["number"],
            issued=spec["issued"],
            vendor=spec["vendor"],
            currency=spec["currency"],
            total=spec["total"],
            subtotal=spec["subtotal"],
            tax=spec["tax"],
            items=spec["items"],
            findings=spec["findings"],
            verdict=spec["verdict"],
            transcript=transcript,
        )
        gt_path = GROUND_TRUTH_DIR / f"{number}.json"
        gt_path.write_text(
            json.dumps(ground_truth, indent=2, ensure_ascii=True),
            encoding="utf-8",
        )
        entries.append(
            {
                "document_id": spec["id"],
                "file_path": f"invoices/{number}{suffix}",
                "file_sha256": hashlib.sha256(data).hexdigest(),
                "mime_type": mime_type,
                "page_count": page_count,
                "license": "synthetic",
                "provenance": "synthetic-fictional-v2",
                "language": spec["slice"][0],
                "quality": spec["slice"][1],
                "layout": spec["slice"][2],
                "ground_truth_path": f"ground_truth/{number}.json",
                "ground_truth_sha256": hashlib.sha256(gt_path.read_bytes()).hexdigest(),
            }
        )
    print(json.dumps(entries, indent=2, ensure_ascii=True))


if __name__ == "__main__":
    main()
