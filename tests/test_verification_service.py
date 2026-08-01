"""API-neutral verification service composition tests."""

from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem
from veridoc.verification.references import HistoricalInvoice, ReferenceLineItem
from veridoc.verification.service import VerificationService


class VerificationRepository:
    """Synthetic repository with a single vendor's safe comparison history."""

    def list_vendor_invoices(self, vendor_key: str) -> list[HistoricalInvoice]:
        assert vendor_key == "fictional-supplies"
        return [
            HistoricalInvoice(
                vendor_key=vendor_key,
                invoice_number=f"INV-{index}",
                currency="USD",
                total=total,
                payment_terms="Net 30",
                line_items=[
                    ReferenceLineItem(
                        product_identifier="CONSULTING",
                        quantity=quantity,
                        unit_price=price,
                    )
                ],
            )
            for index, (total, quantity, price) in enumerate(
                [
                    ("7000.00", "1", "2900.00"),
                    ("7200.00", "2", "3000.00"),
                    ("7400.00", "3", "3100.00"),
                ],
                start=1,
            )
        ]

    def find_invoice(
        self, vendor_key: str, invoice_number: str
    ) -> HistoricalInvoice | None:
        if (vendor_key, invoice_number) == ("fictional-supplies", "INV-001"):
            return HistoricalInvoice(
                vendor_key=vendor_key, invoice_number=invoice_number
            )
        return None

    def get_purchase_order(self, vendor_key: str, purchase_order_number: str) -> None:
        return None


def test_verification_service_returns_no_findings_for_a_normal_invoice() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number="INV-004",
        currency="USD",
        total="7300.00",
        payment_terms="Net 30",
        line_items=[
            InvoiceLineItem(
                product_identifier="CONSULTING", quantity="2", unit_price="3000.00"
            )
        ],
    )

    result = VerificationService(VerificationRepository()).verify(invoice)

    assert result.findings == []


def test_verification_service_combines_repository_and_history_findings() -> None:
    invoice = InvoiceExtraction(
        document_type="invoice",
        vendor_name="Fictional Supplies",
        invoice_number="INV-001",
        currency="USD",
        total="18400.00",
        payment_terms="Due on receipt",
        line_items=[InvoiceLineItem(product_identifier="SOFTWARE", quantity="1")],
    )

    result = VerificationService(VerificationRepository()).verify(invoice)

    finding_types = [finding.finding_type for finding in result.findings]
    assert "duplicate_invoice_number" in finding_types
    assert "historical_total_outlier" in finding_types
    assert "new_line_item" in finding_types
    assert "payment_terms_changed" in finding_types


def test_verification_service_declares_missing_vendor_history() -> None:
    invoice = InvoiceExtraction(document_type="invoice", total="7200.00")

    result = VerificationService(VerificationRepository()).verify(invoice)

    assert [finding.finding_type for finding in result.findings] == [
        "insufficient_history"
    ]
    assert result.findings[0].details == {"metric": "vendor_history"}
