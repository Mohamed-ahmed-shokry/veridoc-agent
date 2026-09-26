"""Tests for local reference-data maintenance commands."""

import json
from datetime import UTC, datetime

from veridoc.administration.cli import main
from veridoc.administration.models import AdminAuditEntryInput
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


def _record_entry(
    repository: SQLiteInvoiceRepository,
    *,
    operation="create",
    record_type="invoice",
    record_id="record-1",
    request_id="request-1",
) -> None:
    repository.record_admin_action(
        AdminAuditEntryInput(
            occurred_at=datetime(2026, 9, 24, 12, 0, 0, tzinfo=UTC),
            request_id=request_id,
            actor="admin",
            operation=operation,
            record_type=record_type,
            record_id=record_id,
            before_json=None,
            after_json='{"invoice_number": "INV-001"}',
        )
    )


def test_cli_audit_log_lists_entries_with_filters(tmp_path, capsys) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    repository = _repository(database_path)
    _record_entry(repository, record_type="invoice", record_id="a")
    _record_entry(repository, record_type="vendor", record_id="b")

    status_all = main(["--database", str(database_path), "audit-log"])
    assert status_all == 0
    all_out = capsys.readouterr().out
    assert "Total audit entries: 2" in all_out
    assert "create invoice:a request=request-1" in all_out

    status_filtered = main(
        [
            "--database",
            str(database_path),
            "audit-log",
            "--record-type",
            "vendor",
        ]
    )
    assert status_filtered == 0
    assert "create vendor:b" in capsys.readouterr().out


def test_cli_audit_log_rejects_out_of_range_pagination(tmp_path, capsys) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    _repository(database_path)

    assert (
        main(
            ["--database", str(database_path), "audit-log", "--limit", "0"],
        )
        == 2
    )
    assert "1 <= --limit <= 200" in capsys.readouterr().err
    assert (
        main(
            ["--database", str(database_path), "audit-log", "--offset", "-1"],
        )
        == 2
    )


def _vendor_input_file(tmp_path, *, vendor_id: str = "vnd_001") -> str:
    path = tmp_path / f"{vendor_id}.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"source": "fixture", "external_id": vendor_id},
                "vendor": {
                    "vendor_id": vendor_id,
                    "legal_name": "Acme Supplies Corp",
                    "canonical_key": "acme-supplies",
                    "status": "active",
                },
            }
        ),
        encoding="utf-8",
    )
    return str(path)


def test_cli_vendors_add_and_update(tmp_path, capsys) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    _repository(database_path)
    input_path = _vendor_input_file(tmp_path)

    status_add = main(
        ["--database", str(database_path), "vendors", "add", "--input", input_path]
    )
    assert status_add == 0
    add_out = capsys.readouterr().out
    assert "Vendor record created: " in add_out
    record_id = add_out.strip().rsplit(" ", 1)[-1]

    update_path = tmp_path / "vnd_001_update.json"
    update_path.write_text(
        '{"vendor": {"vendor_id": "vnd_001", "legal_name": "Acme Supplies Inc", '
        '"canonical_key": "acme-supplies", "status": "active"}}',
        encoding="utf-8",
    )
    status_update = main(
        [
            "--database",
            str(database_path),
            "vendors",
            "update",
            "--record-id",
            record_id,
            "--input",
            str(update_path),
        ]
    )
    assert status_update == 0
    assert f"Vendor record updated: {record_id}" in capsys.readouterr().out

    repository = SQLiteInvoiceRepository(database_path)
    assert repository.get_admin_vendor(record_id) is not None
    entries = repository.list_admin_audit_log(
        record_type="vendor", record_id=record_id, offset=0, limit=200
    )
    assert [entry.operation for entry in entries.records] == ["create", "update"]


def test_cli_vendors_add_reports_conflicts_and_invalid_files(tmp_path, capsys) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    _repository(database_path)
    input_path = _vendor_input_file(tmp_path)

    assert (
        main(
            ["--database", str(database_path), "vendors", "add", "--input", input_path]
        )
        == 0
    )
    capsys.readouterr()
    assert (
        main(
            ["--database", str(database_path), "vendors", "add", "--input", input_path]
        )
        == 1
    )
    assert "reference_data_conflict" in capsys.readouterr().err

    update_path = tmp_path / "vnd_001_update.json"
    update_path.write_text(
        '{"vendor": {"vendor_id": "vnd_001", "legal_name": "Acme Supplies Inc", '
        '"canonical_key": "acme-supplies", "status": "active"}}',
        encoding="utf-8",
    )
    missing_update = main(
        [
            "--database",
            str(database_path),
            "vendors",
            "update",
            "--record-id",
            "missing-record",
            "--input",
            str(update_path),
        ]
    )
    assert missing_update == 1
    assert "not found" in capsys.readouterr().err

    bad_path = tmp_path / "bad.json"
    bad_path.write_text('{"vendor": {}}', encoding="utf-8")
    assert (
        main(
            [
                "--database",
                str(database_path),
                "vendors",
                "add",
                "--input",
                str(bad_path),
            ]
        )
        == 1
    )
    assert "invalid" in capsys.readouterr().err

    assert (
        main(
            [
                "--database",
                str(database_path),
                "vendors",
                "add",
                "--input",
                str(tmp_path / "missing.json"),
            ]
        )
        == 1
    )
    assert "could not be read" in capsys.readouterr().err


def test_cli_vendors_delete_writes_an_audit_entry(tmp_path, capsys) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    _repository(database_path)
    input_path = _vendor_input_file(tmp_path)
    assert (
        main(
            ["--database", str(database_path), "vendors", "add", "--input", input_path]
        )
        == 0
    )
    capsys.readouterr()
    repository = SQLiteInvoiceRepository(database_path)
    record_id = (
        repository.list_admin_vendors(status=None, offset=0, limit=1)
        .records[0]
        .metadata.record_id
    )

    assert (
        main(
            [
                "--database",
                str(database_path),
                "vendors",
                "delete",
                "--record-id",
                record_id,
            ]
        )
        == 0
    )
    capsys.readouterr()
    entries = repository.list_admin_audit_log(
        record_type="vendor", record_id=record_id, offset=0, limit=200
    )
    assert [entry.operation for entry in entries.records] == ["create", "delete"]
    assert entries.records[1].after_json is None


def _invoice_input_file(tmp_path) -> str:
    path = tmp_path / "invoice.json"
    path.write_text(
        json.dumps(
            {
                "metadata": {"source": "fixture", "external_id": "invoice-1"},
                "invoice": {
                    "vendor_key": "fictional-supplies",
                    "invoice_number": "INV-001",
                    "currency": "USD",
                    "total": "42.00",
                },
            }
        ),
        encoding="utf-8",
    )
    return str(path)


def test_cli_invoices_add_update_and_delete(tmp_path, capsys) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    _repository(database_path)
    input_path = _invoice_input_file(tmp_path)

    assert (
        main(
            [
                "--database",
                str(database_path),
                "invoices",
                "add",
                "--input",
                input_path,
            ]
        )
        == 0
    )
    add_out = capsys.readouterr().out
    assert "Invoice record created: " in add_out
    record_id = add_out.strip().rsplit(" ", 1)[-1]

    update_path = tmp_path / "invoice-update.json"
    update_path.write_text(
        '{"invoice": {"vendor_key": "fictional-supplies", '
        '"invoice_number": "INV-002"}}',
        encoding="utf-8",
    )
    assert (
        main(
            [
                "--database",
                str(database_path),
                "invoices",
                "update",
                "--record-id",
                record_id,
                "--input",
                str(update_path),
            ]
        )
        == 0
    )
    assert f"Invoice record updated: {record_id}" in capsys.readouterr().out
    assert (
        main(
            [
                "--database",
                str(database_path),
                "invoices",
                "delete",
                "--record-id",
                record_id,
            ]
        )
        == 0
    )
    assert f"Invoice record deleted: {record_id}" in capsys.readouterr().out

    repository = SQLiteInvoiceRepository(database_path)
    entries = repository.list_admin_audit_log(
        record_type="invoice", record_id=record_id, offset=0, limit=200
    )
    assert [entry.operation for entry in entries.records] == [
        "create",
        "update",
        "delete",
    ]


def test_cli_invoices_reports_conflicts_and_bad_inputs(tmp_path, capsys) -> None:
    database_path = tmp_path / "reference-data.sqlite"
    _repository(database_path)
    input_path = _invoice_input_file(tmp_path)
    add = [
        "--database",
        str(database_path),
        "invoices",
        "add",
        "--input",
        input_path,
    ]

    assert main(add) == 0
    capsys.readouterr()
    assert main(add) == 1
    assert "reference_data_conflict" in capsys.readouterr().err

    bad_path = tmp_path / "bad.json"
    bad_path.write_text('{"invoice": {}}', encoding="utf-8")
    assert (
        main(
            [
                "--database",
                str(database_path),
                "invoices",
                "add",
                "--input",
                str(bad_path),
            ]
        )
        == 1
    )
    assert "invalid" in capsys.readouterr().err

    assert (
        main(
            [
                "--database",
                str(database_path),
                "invoices",
                "delete",
                "--record-id",
                "missing-record",
            ]
        )
        == 1
    )
    assert "not found" in capsys.readouterr().err
