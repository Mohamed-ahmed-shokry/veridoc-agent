"""Tesseract adapter tests using deterministic mocked engine output."""

from typing import Any

import pytest
from PIL import Image

from veridoc.ocr import tesseract
from veridoc.ocr.protocol import OCRUnavailableError


def test_tesseract_parses_lines_and_averages_word_confidence(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    output: dict[str, list[Any]] = {
        "text": ["Fictional", "Vendor", "Total", "120.00", ""],
        "conf": ["90", "80", "-1", "70", "-1"],
        "block_num": [1, 1, 2, 2, 2],
        "par_num": [1, 1, 1, 1, 1],
        "line_num": [1, 1, 1, 1, 1],
    }

    def fake_image_to_data(*args: Any, **kwargs: Any) -> dict[str, list[Any]]:
        del args, kwargs
        return output

    monkeypatch.setattr(tesseract.pytesseract, "image_to_data", fake_image_to_data)
    previous_command = tesseract.pytesseract.pytesseract.tesseract_cmd

    result = tesseract.TesseractEngine(
        command="fake-tesseract", language="eng+ara"
    ).recognize(Image.new("RGB", (2, 2)))

    assert result.text == "Fictional Vendor\nTotal 120.00"
    assert result.confidence == 80.0
    assert tesseract.pytesseract.pytesseract.tesseract_cmd == previous_command


def test_tesseract_missing_executable_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_executable(*args: Any, **kwargs: Any) -> dict[str, list[Any]]:
        del args, kwargs
        raise tesseract.TesseractNotFoundError()

    monkeypatch.setattr(tesseract.pytesseract, "image_to_data", missing_executable)

    with pytest.raises(OCRUnavailableError, match="not available"):
        tesseract.TesseractEngine().recognize(Image.new("RGB", (2, 2)))
