# ADR 0001: Use Tesseract as the Version 1 OCR Baseline

## Status

Accepted on 2026-08-01.

## Context

Phase 1 needs one replaceable OCR baseline for invoice images and rendered PDF
pages. Veridoc must support Latin and Arabic invoice content without coupling
upload validation or future extraction logic to one vendor SDK. The local
development environment must also remain practical on Windows and in CI.

## Decision

Use Tesseract through the `pytesseract` Python adapter. The OCR boundary accepts
decoded page images and returns typed page text and confidence values. Tesseract
is invoked only after upload size, signature, document, page, and image limits
have passed. The default language is `eng`; deployments processing Arabic must
install the Arabic trained data and set `TESSERACT_LANG=eng+ara`.

## Alternatives considered

- PaddleOCR: strong multilingual and layout capabilities, but its larger model
  and runtime footprint are not justified for the first replaceable baseline.
- A direct subprocess wrapper: would avoid the Python adapter but would spread
  executable and output parsing concerns beyond the typed OCR boundary.

## Consequences

The typed OCR boundary keeps Tesseract replaceable and lets tests use
deterministic engines without an installed executable. Runtime environments
must install and maintain the executable and every required language data file.

Tesseract is sensitive to scan quality, skew, font choice, and page layout. It
does not provide document understanding or invoice field extraction. Word-level
confidence is available when the executable returns it, but confidence is not a
calibrated probability and must not be used as a verification verdict. PDF pages
are rasterized before OCR, which can lose vector text semantics and increases
processing cost. Phase 1 does not implement structured extraction, anomaly
detection, or a second OCR engine.

## Installation and runtime

Install the Tesseract executable separately from Python dependencies. On
Windows, the verified winget package can be installed with:

```powershell
winget install --id UB-Mannheim.TesseractOCR --exact --accept-source-agreements --accept-package-agreements
```

Add its installation directory to `PATH`, or set `TESSERACT_CMD` to the
executable path. Install the English trained data and the Arabic trained data
when Arabic invoices are in scope. On Debian/Ubuntu,
install `tesseract-ocr`, `tesseract-ocr-eng`, and `tesseract-ocr-ara` with the
system package manager. Then synchronize this repository with:

```bash
uv sync --all-groups --locked
```

The service uses `TESSERACT_LANG=eng` by default. Set `TESSERACT_LANG=eng+ara`
for bilingual processing. If the executable or requested language data is
missing, the API returns a safe OCR-unavailable error rather than pretending
that text was extracted.
