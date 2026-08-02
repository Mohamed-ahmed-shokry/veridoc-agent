"""Tesseract OCR adapter with typed output and safe failure handling."""

from __future__ import annotations

import os
from collections import defaultdict
from threading import RLock
from typing import Any

import pytesseract
from PIL import Image
from pytesseract import Output
from pytesseract.pytesseract import TesseractError, TesseractNotFoundError

from veridoc.ocr.models import OCRPageResult
from veridoc.ocr.protocol import OCRUnavailableError

_TESSERACT_LOCK = RLock()


class TesseractEngine:
    """Run Tesseract for one image and return text with word confidence."""

    def __init__(
        self, *, command: str | None = None, language: str | None = None
    ) -> None:
        self.command = command or os.getenv("TESSERACT_CMD")
        configured_language = language or os.getenv("TESSERACT_LANG", "eng")
        if configured_language is None or not configured_language.strip():
            raise ValueError("TESSERACT_LANG must not be empty")
        self.language = configured_language

    def recognize(self, image: Image.Image) -> OCRPageResult:
        """Recognize one image, translating executable failures to a safe error."""
        with _TESSERACT_LOCK:
            previous_command = pytesseract.pytesseract.tesseract_cmd
            if self.command:
                pytesseract.pytesseract.tesseract_cmd = self.command
            try:
                data = pytesseract.image_to_data(
                    image,
                    lang=self.language,
                    output_type=Output.DICT,
                )
            except (OSError, TesseractError, TesseractNotFoundError) as exc:
                raise OCRUnavailableError from exc
            finally:
                pytesseract.pytesseract.tesseract_cmd = previous_command
        return _parse_data(data)


def _parse_data(data: dict[str, list[Any]]) -> OCRPageResult:
    lines: dict[tuple[int, int, int], list[str]] = defaultdict(list)
    confidences: list[float] = []
    texts = data.get("text", [])
    for index, raw_text in enumerate(texts):
        text = str(raw_text).strip()
        if not text:
            continue
        key = (
            _integer_at(data.get("block_num"), index),
            _integer_at(data.get("par_num"), index),
            _integer_at(data.get("line_num"), index),
        )
        lines[key].append(text)
        confidence = _float_at(data.get("conf"), index)
        if confidence is not None and confidence >= 0:
            confidences.append(confidence)

    return OCRPageResult(
        text="\n".join(" ".join(words) for words in lines.values()),
        confidence=(sum(confidences) / len(confidences) if confidences else None),
    )


def _integer_at(values: list[Any] | None, index: int) -> int:
    if not values or index >= len(values):
        return 0
    try:
        return int(values[index])
    except (TypeError, ValueError):
        return 0


def _float_at(values: list[Any] | None, index: int) -> float | None:
    if not values or index >= len(values):
        return None
    try:
        return float(values[index])
    except (TypeError, ValueError):
        return None
