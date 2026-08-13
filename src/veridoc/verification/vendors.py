"""Stable vendor keys for repository-backed verification."""

from __future__ import annotations

import re

from veridoc.extraction.models import InvoiceExtraction

_SEPARATOR = re.compile(r"[\W_]+")


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
