"""SQLite integration tests for atomic reference-data imports."""

import pytest

from veridoc.administration.models import (
    InvoiceRecordInput,
    InvoiceReferenceInput,
    PurchaseOrderRecordInput,
    PurchaseOrderReferenceInput,
    ReferenceDataImport,
    ReferenceMetadataInput,
)
from veridoc.administration.protocol import (
    ReferenceDataAdminRepository,
    ReferenceDataConflictError,
)
from veridoc.persistence.sqlite import SQLiteInvoiceRepository


def _repository(tmp_path) -> SQLiteInvoiceRepository:
    repository = SQLiteInvoiceRepository(tmp_path / "reference-data.sqlite")
    repository.initialize()
    return repository


def _invoice(external_id: str, invoice_number: str) -> InvoiceRecordInput:
    return InvoiceRecordInput(
        metadata=ReferenceMetadataInput(source="fixture", external_id=external_id),
        invoice=InvoiceReferenceInput(
            vendor_key="fictional-supplies",
            invoice_number=invoice_number,
            total="42.00",
        ),
    )


def _purchase_order(
    external_id: str, purchase_order_number: str
) -> PurchaseOrderRecordInput:
    return PurchaseOrderRecordInput(
        metadata=ReferenceMetadataInput(source="fixture", external_id=external_id),
        purchase_order=PurchaseOrderReferenceInput(
            vendor_key="fictional-supplies",
            purchase_order_number=purchase_order_number,
            total="42.00",
        ),
    )


def test_import_creates_invoice_and_purchase_order_in_one_transaction(tmp_path) -> None:
    repository = _repository(tmp_path)
    batch = ReferenceDataImport(
        invoices=[_invoice("invoice-1", "INV-001")],
        purchase_orders=[_purchase_order("purchase-order-1", "PO-001")],
    )

    result = repository.import_reference_data(batch, conflict="reject", dry_run=False)

    assert isinstance(repository, ReferenceDataAdminRepository)
    assert result.model_dump() == {
        "dry_run": False,
        "created": 2,
        "replaced": 0,
        "skipped": 0,
    }
    assert repository.list_invoices(vendor_key=None, offset=0, limit=100).total == 1
    assert (
        repository.list_purchase_orders(vendor_key=None, offset=0, limit=100).total == 1
    )


def test_import_dry_run_reports_changes_without_persisting_them(tmp_path) -> None:
    repository = _repository(tmp_path)
    batch = ReferenceDataImport(
        invoices=[_invoice("invoice-1", "INV-001")],
        purchase_orders=[_purchase_order("purchase-order-1", "PO-001")],
    )

    result = repository.import_reference_data(batch, conflict="reject", dry_run=True)

    assert result.created == 2
    assert result.dry_run is True
    assert repository.list_invoices(vendor_key=None, offset=0, limit=100).total == 0
    assert (
        repository.list_purchase_orders(vendor_key=None, offset=0, limit=100).total == 0
    )


def test_reject_import_rolls_back_records_before_a_conflict(tmp_path) -> None:
    repository = _repository(tmp_path)
    repository.create_invoice(_invoice("invoice-existing", "INV-EXISTING"))
    batch = ReferenceDataImport(
        invoices=[
            _invoice("invoice-new", "INV-NEW"),
            _invoice("invoice-existing", "INV-CONFLICT"),
        ]
    )

    with pytest.raises(ReferenceDataConflictError):
        repository.import_reference_data(batch, conflict="reject", dry_run=False)

    page = repository.list_invoices(vendor_key=None, offset=0, limit=100)
    assert page.total == 1
    assert page.records[0].invoice.invoice_number == "INV-EXISTING"


def test_skip_import_keeps_conflicts_and_creates_new_records(tmp_path) -> None:
    repository = _repository(tmp_path)
    existing = repository.create_invoice(_invoice("invoice-existing", "INV-EXISTING"))
    batch = ReferenceDataImport(
        invoices=[
            _invoice("invoice-existing", "INV-IGNORED"),
            _invoice("invoice-new", "INV-NEW"),
        ]
    )

    result = repository.import_reference_data(batch, conflict="skip", dry_run=False)

    assert result.created == 1
    assert result.skipped == 1
    assert (
        repository.get_admin_invoice(existing.metadata.record_id).invoice.invoice_number
        == "INV-EXISTING"
    )


def test_replace_import_preserves_identity_and_replaces_facts(tmp_path) -> None:
    repository = _repository(tmp_path)
    existing = repository.create_invoice(_invoice("invoice-existing", "INV-EXISTING"))
    batch = ReferenceDataImport(invoices=[_invoice("invoice-existing", "INV-REPLACED")])

    result = repository.import_reference_data(batch, conflict="replace", dry_run=False)
    replaced = repository.get_admin_invoice(existing.metadata.record_id)

    assert result.replaced == 1
    assert replaced is not None
    assert replaced.metadata.record_id == existing.metadata.record_id
    assert replaced.invoice.invoice_number == "INV-REPLACED"


def test_replace_import_rejects_purchase_order_owned_by_other_provenance(
    tmp_path,
) -> None:
    repository = _repository(tmp_path)
    repository.create_purchase_order(_purchase_order("po-existing", "PO-001"))
    batch = ReferenceDataImport(
        invoices=[_invoice("invoice-new", "INV-NEW")],
        purchase_orders=[_purchase_order("po-other", "PO-001")],
    )

    with pytest.raises(ReferenceDataConflictError):
        repository.import_reference_data(batch, conflict="replace", dry_run=False)

    assert repository.list_invoices(vendor_key=None, offset=0, limit=100).total == 0
