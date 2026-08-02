"""Tests for local reference-data maintenance commands."""

from veridoc.administration.cli import main
from veridoc.persistence.sqlite import SQLiteInvoiceRepository
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
