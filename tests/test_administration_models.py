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
    VendorBankAccountInput,
    VendorInput,
    VendorRecordInput,
    VendorTaxIdInput,
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


def _vendor_record(external_id: str = "vendor-1") -> VendorRecordInput:
    return VendorRecordInput(
        metadata=ReferenceMetadataInput(source="fixture", external_id=external_id),
        vendor=VendorInput(
            vendor_id="vnd_001",
            legal_name="Acme Corp",
            canonical_key="acme-corp",
            status="active",
            aliases=["Acme"],
            bank_accounts=[
                VendorBankAccountInput(
                    account_number="12345678",
                    iban="GB29NWBK60161331926819",
                )
            ],
            tax_ids=[VendorTaxIdInput(tax_id="GB123456789")],
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


def test_administration_models_canonicalize_vendor_keys() -> None:
    invoice = InvoiceReferenceInput(vendor_key=" SUPPLIER / 001 ")
    purchase_order = PurchaseOrderReferenceInput(
        vendor_key="SUPPLIER___001",
        purchase_order_number="PO-001",
    )

    assert invoice.vendor_key == "supplier-001"
    assert purchase_order.vendor_key == "supplier-001"

    with pytest.raises(ValidationError):
        InvoiceReferenceInput(vendor_key="___")


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


def test_vendor_input_converts_to_domain_and_normalizes_key() -> None:
    vendor = VendorInput(
        vendor_id="vnd_001",
        legal_name="  Acme Corporation Ltd.  ",
        canonical_key=" ACME CORP ",
        status="active",
        aliases=["Acme"],
        bank_accounts=[
            VendorBankAccountInput(
                account_number="12345678",
                iban="GB29NWBK60161331926819",
            )
        ],
        tax_ids=[VendorTaxIdInput(tax_id="GB123456789")],
    )

    assert vendor.legal_name == "Acme Corporation Ltd."
    assert vendor.canonical_key == "acme-corp"
    domain = vendor.to_domain()
    assert domain.vendor_id == "vnd_001"
    assert domain.canonical_key == "acme-corp"
    assert len(domain.bank_accounts) == 1
    assert domain.bank_accounts[0].iban == "GB29NWBK60161331926819"
    assert len(domain.tax_ids) == 1
    assert domain.tax_ids[0].tax_id == "GB123456789"


def test_vendor_input_rejects_invalid_vendor_id() -> None:
    with pytest.raises(ValidationError):
        VendorInput(
            vendor_id="-invalid!",
            legal_name="Acme",
            canonical_key="acme",
        )


def test_import_accepts_vendor_records_and_bounds_batch() -> None:
    vendors = [_vendor_record(f"vendor-{index}") for index in range(250)]
    invoices = [_invoice_record(f"invoice-{index}") for index in range(250)]
    batch = ReferenceDataImport(invoices=invoices, vendors=vendors)
    assert len(batch.invoices) == 250
    assert len(batch.vendors) == 250

    with pytest.raises(ValidationError):
        ReferenceDataImport(
            invoices=invoices,
            vendors=vendors + [_vendor_record("vendor-overflow")],
        )
