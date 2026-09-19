"""Tests for local reference-data maintenance commands."""

from veridoc.administration.cli import main
from veridoc.persistence.sqlite import SQLiteInvoiceRepository
from veridoc.vendors.models import VendorBankAccount, VendorEntity, VendorTaxId
from veridoc.verification.references import HistoricalInvoice


def _repository(path) -> SQLiteInvoiceRepository:
    repository = SQLiteInvoiceRepository(path)
    repository.initialize()
    return repository


def _add_invoice(repository: SQLiteInvoiceRepository, number: str) -> None:
    repository.add_invoice(
        HistoricalInvoice(vendor_key="fictional-supplies", invoice_number=number)
    )


def test_cli_backs_up_and_restores_with_explicit_confirmation(tmp_path, capsys) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    backup_path = tmp_path / "reference-data.backup.sqlite"
    repository = _repository(database_path)
    _add_invoice(repository, "INV-BACKUP")

    backup_status = main(
        [
            "--database",
            str(database_path),
            "backup",
            "--output",
            str(backup_path),
        ]
    )
    repository.delete_admin_invoice(
        repository.list_invoices(vendor_key=None, offset=0, limit=1)
        .records[0]
        .metadata.record_id
    )
    refused_status = main(
        [
            "--database",
            str(database_path),
            "restore",
            "--input",
            str(backup_path),
        ]
    )
    restore_status = main(
        [
            "--database",
            str(database_path),
            "restore",
            "--input",
            str(backup_path),
            "--confirm-replace",
        ]
    )

    restored = _repository(database_path)
    output = capsys.readouterr()
    assert backup_status == 0
    assert refused_status == 2
    assert restore_status == 0
    assert "Restore requires --confirm-replace." in output.err
    assert restored.find_invoice("fictional-supplies", "INV-BACKUP") is not None


def test_cli_returns_a_generic_error_without_exposing_missing_paths(
    tmp_path, capsys
) -> None:
    missing_path = tmp_path / "private-missing.sqlite"

    status = main(
        [
            "--database",
            str(missing_path),
            "backup",
            "--output",
            str(tmp_path / "backup.sqlite"),
        ]
    )

    output = capsys.readouterr()
    assert status == 1
    assert "maintenance could not be completed safely" in output.err
    assert str(missing_path) not in output.err


def test_cli_vendors_list_and_get(tmp_path, capsys) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    repository = _repository(database_path)
    repository.add_vendor(
        VendorEntity(
            vendor_id="vnd_001",
            legal_name="Acme Corporation",
            canonical_key="acme-corporation",
            status="active",
            aliases=["Acme"],
            bank_accounts=[
                VendorBankAccount(
                    account_number="12345678",
                    iban="GB29NWBK60161331926819",
                )
            ],
            tax_ids=[VendorTaxId(tax_id="GB123456789")],
        )
    )

    # List vendors
    status_list = main(
        [
            "--database",
            str(database_path),
            "vendors",
            "list",
        ]
    )
    assert status_list == 0
    list_out = capsys.readouterr().out
    assert "Total vendors: 1" in list_out
    assert "vnd_001: Acme Corporation (acme-corporation)" in list_out

    # Get vendor
    status_get = main(
        [
            "--database",
            str(database_path),
            "vendors",
            "get",
            "--vendor-id",
            "vnd_001",
        ]
    )
    assert status_get == 0
    get_out = capsys.readouterr().out
    assert "Vendor ID: vnd_001" in get_out
    assert "Legal Name: Acme Corporation" in get_out
    assert "Aliases: Acme" in get_out
    assert "GB123456789" in get_out
    assert "12345678 (IBAN: GB29NWBK60161331926819)" in get_out

    # Get nonexistent vendor
    status_missing = main(
        [
            "--database",
            str(database_path),
            "vendors",
            "get",
            "--vendor-id",
            "vnd_missing",
        ]
    )
    assert status_missing == 1
    missing_err = capsys.readouterr().err
    assert "Vendor not found: vnd_missing" in missing_err


def test_cli_vendors_delete(tmp_path, capsys) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    repository = _repository(database_path)
    repository.add_vendor(
        VendorEntity(
            vendor_id="vnd_001",
            legal_name="Acme Corp",
            canonical_key="acme-corp",
            status="active",
        )
    )
    record = repository.list_admin_vendors(status=None, offset=0, limit=1).records[0]
    record_id = record.metadata.record_id

    # Delete existing
    status_del = main(
        [
            "--database",
            str(database_path),
            "vendors",
            "delete",
            "--record-id",
            record_id,
        ]
    )
    assert status_del == 0
    assert f"Vendor record deleted: {record_id}" in capsys.readouterr().out

    # Delete missing
    status_del_missing = main(
        [
            "--database",
            str(database_path),
            "vendors",
            "delete",
            "--record-id",
            record_id,
        ]
    )
    assert status_del_missing == 1
    assert f"Vendor record not found: {record_id}" in capsys.readouterr().err
