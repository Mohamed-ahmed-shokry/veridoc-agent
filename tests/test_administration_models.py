"""Validation tests for bounded administrative schemas."""

from decimal import Decimal

import pytest
from pydantic import ValidationError

from veridoc.administration.models import (
    MAX_IMPORT_RECORDS,
    MAX_REFERENCE_LINE_ITEMS,
    InvoiceRecordInput,
    InvoiceReferenceInput,
    PurchaseOrderRecordInput,
    PurchaseOrderReferenceInput,
    ReferenceDataImport,
    ReferenceLineItemInput,
    ReferenceMetadataInput,
)


def _invoice_record(external_id: str = "invoice-1") -> InvoiceRecordInput:
    return InvoiceRecordInput(
        metadata=ReferenceMetadataInput(source="fixture", external_id=external_id),
        invoice=InvoiceReferenceInput(
            vendor_key="fictional-supplies",
            invoice_number="INV-001",
            total="42.00",
        ),
    )


def _purchase_order_record(
    external_id: str = "purchase-order-1",
) -> PurchaseOrderRecordInput:
    return PurchaseOrderRecordInput(
        metadata=ReferenceMetadataInput(source="fixture", external_id=external_id),
        purchase_order=PurchaseOrderReferenceInput(
            vendor_key="fictional-supplies",
            purchase_order_number="PO-001",
            total="42.00",
        ),
    )


def test_administration_models_strip_metadata_and_convert_domain_facts() -> None:
    record = InvoiceRecordInput(
        metadata={"source": " fixture ", "external_id": " invoice-1 "},
        invoice={"vendor_key": " fictional-supplies ", "total": "42.00"},
    )

    assert record.metadata.source == "fixture"
    assert record.metadata.external_id == "invoice-1"
    assert record.invoice.to_domain().vendor_key == "fictional-supplies"


def test_administration_models_reject_non_finite_amounts_and_extra_fields() -> None:
    with pytest.raises(ValidationError):
        InvoiceReferenceInput(vendor_key="fictional", total=Decimal("NaN"))

    with pytest.raises(ValidationError):
        ReferenceMetadataInput(source="fixture", external_id="invoice-1", token="x")


def test_invoice_inputs_bound_line_item_count() -> None:
    line_items = [ReferenceLineItemInput()] * (MAX_REFERENCE_LINE_ITEMS + 1)

    with pytest.raises(ValidationError):
        InvoiceReferenceInput(vendor_key="fictional", line_items=line_items)


def test_import_requires_records_and_bounds_the_combined_batch() -> None:
    with pytest.raises(ValidationError):
        ReferenceDataImport()

    invoices = [_invoice_record(f"invoice-{index}") for index in range(251)]
    purchase_orders = [
        _purchase_order_record(f"purchase-order-{index}") for index in range(250)
    ]

    with pytest.raises(ValidationError):
        ReferenceDataImport(invoices=invoices, purchase_orders=purchase_orders)

    assert len(invoices) + len(purchase_orders) == MAX_IMPORT_RECORDS + 1


def test_metadata_rejects_control_characters_and_unsafe_identifiers() -> None:
    with pytest.raises(ValidationError):
        ReferenceMetadataInput(source="fixture\nforged", external_id="invoice-1")

    with pytest.raises(ValidationError):
        ReferenceMetadataInput(source="fixture", external_id="invoice id")
