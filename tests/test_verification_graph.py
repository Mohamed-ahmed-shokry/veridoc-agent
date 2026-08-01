"""Verification graph composition tests."""

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.graph import build_verification_graph
from veridoc.verification.references import HistoricalInvoice, PurchaseOrder
from veridoc.verification.service import VerificationService


class EmptyRepository:
    """Repository double for graph wiring without external I/O."""

    def list_vendor_invoices(self, vendor_key: str) -> list[HistoricalInvoice]:
        return []

    def find_invoice(
        self, vendor_key: str, invoice_number: str
    ) -> HistoricalInvoice | None:
        return None

    def get_purchase_order(
        self, vendor_key: str, purchase_order_number: str
    ) -> PurchaseOrder | None:
        return None


def test_verification_graph_runs_the_service_node() -> None:
    graph = build_verification_graph(VerificationService(EmptyRepository()))
    extraction = InvoiceExtraction(document_type="invoice")

    result = graph.invoke({"extraction": extraction})

    assert result["extraction"] == extraction
    assert result["verification"].findings == []
