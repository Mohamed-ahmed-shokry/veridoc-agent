"""Repository-backed verification tests."""

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.references import HistoricalInvoice
from veridoc.verification.repository_checks import check_duplicate_invoice_number


class DuplicateInvoiceRepository:
    """Minimal synthetic lookup used for deterministic duplicate tests."""

    def find_invoice(
        self, vendor_key: str, invoice_number: str
    ) -> HistoricalInvoice | None:
        if (vendor_key, invoice_number) == ("fictional-supplies", "INV-001"):
            return HistoricalInvoice(
                vendor_key=vendor_key,
                invoice_number=invoice_number,
                invoice_date="2026-07-01",
            )
        return None


def test_duplicate_invoice_check_reports_a_matching_historical_invoice() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number="INV-001",
    )

    findings = check_duplicate_invoice_number(invoice, DuplicateInvoiceRepository())

    assert len(findings) == 1
    assert findings[0].finding_type == "duplicate_invoice_number"
    assert findings[0].details == {
        "vendor_key": "fictional-supplies",
        "existing_invoice_date": "2026-07-01",
    }


def test_duplicate_invoice_check_skips_absent_identifiers_and_unknown_invoices() -> (
    None
):
    repository = DuplicateInvoiceRepository()

    assert (
        check_duplicate_invoice_number(
            InvoiceExtraction(
                document_type="invoice", vendor_name="Fictional Supplies"
            ),
            repository,
        )
        == []
    )
    assert (
        check_duplicate_invoice_number(
            InvoiceExtraction(
                document_type="invoice",
                vendor_name="Fictional Supplies",
                invoice_number="INV-404",
            ),
            repository,
        )
        == []
    )
