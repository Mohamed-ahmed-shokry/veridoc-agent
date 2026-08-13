"""Vendor-key resolution tests."""

import pytest

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.vendors import normalize_vendor_key, vendor_key_for


def test_vendor_key_prefers_the_extracted_vendor_identifier() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies Ltd.",
        vendor_identifier="SUPPLIER / 001",
    )

    assert vendor_key_for(invoice) == "supplier-001"


@pytest.mark.parametrize("vendor_identifier", ["   ", "___"])
def test_vendor_key_falls_back_when_the_identifier_cannot_be_normalized(
    vendor_identifier: str,
) -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies Ltd.",
        vendor_identifier=vendor_identifier,
    )

    assert vendor_key_for(invoice) == "fictional-supplies-ltd"


def test_vendor_key_normalizes_a_vendor_name_and_handles_absence() -> None:
    assert (
        vendor_key_for(
            InvoiceExtraction(
                document_type="invoice", vendor_name="  Fictiönal--Supplies  "
            )
        )
        == "fictiönal-supplies"
    )
    assert vendor_key_for(InvoiceExtraction(document_type="invoice")) is None


def test_vendor_key_normalization_is_reusable_without_an_extraction() -> None:
    assert normalize_vendor_key(" SUPPLIER / 001 ") == "supplier-001"
    assert normalize_vendor_key("___") is None
    assert normalize_vendor_key(None) is None
