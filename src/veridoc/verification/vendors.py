"""Stable vendor and invoice-number keys for repository-backed verification."""

from __future__ import annotations

import re
import unicodedata

from veridoc.extraction.models import InvoiceExtraction

_SEPARATOR = re.compile(r"[\W_]+")
_DASH_LIKE = re.compile("[\u2010-\u2015\u2212\ufe58\ufe63\uff0d]")
_WHITESPACE = re.compile(r"\s+")


def vendor_key_for(invoice: InvoiceExtraction) -> str | None:
    """Return a normalized vendor identifier or name when one is present."""
    return normalize_vendor_key(invoice.vendor_identifier) or normalize_vendor_key(
        invoice.vendor_name
    )


def normalize_vendor_key(raw_value: str | None) -> str | None:
    """Return the canonical repository key for one vendor value."""
    if raw_value is None:
        return None
    normalized = _SEPARATOR.sub("-", raw_value.casefold()).strip("-")
    return normalized or None


def normalize_invoice_number(raw_value: str | None) -> str | None:
    """Return the canonical identity for one invoice number.

    NFKC normalization, dash-like characters folded to hyphen-minus,
    whitespace removed, and casefolded — so OCR and provider variants of
    one number (`INV-001`, `inv 001`) share one identity while hyphenated
    and unhyphenated forms stay distinct.
    """
    if raw_value is None:
        return None
    folded = _DASH_LIKE.sub("-", unicodedata.normalize("NFKC", raw_value))
    normalized = _WHITESPACE.sub("", folded).casefold()
    return normalized or None
