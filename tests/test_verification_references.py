"""Reference record and repository boundary tests."""

import pytest
from pydantic import ValidationError

from veridoc.verification.references import HistoricalInvoice, PurchaseOrder


def test_reference_records_preserve_optional_invoice_facts() -> None:
    invoice = HistoricalInvoice(
        vendor_key="fictional-supplies",
        invoice_number="INV-001",
        currency="USD",
        total="7200.00",
    )
    purchase_order = PurchaseOrder(
        vendor_key="fictional-supplies",
        purchase_order_number="PO-001",
        currency="USD",
        total="7200.00",
    )

    assert invoice.total == 7200
    assert purchase_order.purchase_order_number == "PO-001"


def test_reference_records_reject_invalid_vendor_and_currency() -> None:
    with pytest.raises(ValidationError):
        HistoricalInvoice(vendor_key="", currency="USD")
    with pytest.raises(ValidationError):
        PurchaseOrder(
            vendor_key="fictional-supplies",
            purchase_order_number="PO-001",
            currency="usd",
        )
