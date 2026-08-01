"""Stable vendor keys for repository-backed verification."""

from __future__ import annotations

import re

from veridoc.extraction.models import InvoiceExtraction

_SEPARATOR = re.compile(r"[\W_]+")


def vendor_key_for(invoice: InvoiceExtraction) -> str | None:
    """Return a normalized vendor identifier or name when one is present."""
    raw_value = invoice.vendor_identifier or invoice.vendor_name
    if raw_value is None:
        return None
    normalized = _SEPARATOR.sub("-", raw_value.casefold()).strip("-")
    return normalized or None
