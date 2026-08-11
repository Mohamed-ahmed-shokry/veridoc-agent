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

    observed_kwargs: dict[str, Any] = {}

    def fake_image_to_data(*args: Any, **kwargs: Any) -> dict[str, list[Any]]:
        del args
        observed_kwargs.update(kwargs)
        return output

    monkeypatch.setattr(tesseract.pytesseract, "image_to_data", fake_image_to_data)
    previous_command = tesseract.pytesseract.pytesseract.tesseract_cmd

    result = tesseract.TesseractEngine(
        command="fake-tesseract", language="eng+ara"
    ).recognize(Image.new("RGB", (2, 2)))

    assert result.text == "Fictional Vendor\nTotal 120.00"
    assert result.confidence == 80.0
    assert observed_kwargs["timeout"] == 30.0
    assert tesseract.pytesseract.pytesseract.tesseract_cmd == previous_command


def test_tesseract_missing_executable_is_safe(monkeypatch: pytest.MonkeyPatch) -> None:
    def missing_executable(*args: Any, **kwargs: Any) -> dict[str, list[Any]]:
        del args, kwargs
        raise tesseract.TesseractNotFoundError()

    monkeypatch.setattr(tesseract.pytesseract, "image_to_data", missing_executable)

    with pytest.raises(OCRUnavailableError, match="not available"):
        tesseract.TesseractEngine().recognize(Image.new("RGB", (2, 2)))


def test_tesseract_ignores_invalid_confidence_values() -> None:
    result = tesseract._parse_data(
        {
            "text": ["Valid", "NaN", "Infinite", "TooHigh"],
            "conf": ["75", "nan", "inf", "101"],
        }
    )

    assert result.text == "Valid NaN Infinite TooHigh"
    assert result.confidence == 75.0


def test_tesseract_timeout_is_reported_safely(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def stalled_process(*args: Any, **kwargs: Any) -> dict[str, list[Any]]:
        del args, kwargs
        raise RuntimeError("Tesseract process timeout")

    monkeypatch.setattr(tesseract.pytesseract, "image_to_data", stalled_process)

    with pytest.raises(OCRUnavailableError, match="not available"):
        tesseract.TesseractEngine(timeout_seconds=0.25).recognize(
            Image.new("RGB", (2, 2))
        )


@pytest.mark.parametrize("configured", ["0", "301", "nan", "not-a-number"])
def test_tesseract_rejects_unbounded_timeouts(
    configured: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("TESSERACT_TIMEOUT_SECONDS", configured)

    with pytest.raises(ValueError, match="TESSERACT_TIMEOUT_SECONDS"):
        tesseract.TesseractEngine()
