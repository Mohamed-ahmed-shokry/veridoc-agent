"""Deterministic document type verification tests."""

from datetime import date
from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem
from veridoc.verification.document_type import check_document_type


def _invoice(**kwargs: object) -> InvoiceExtraction:
    """Build an InvoiceExtraction with default or overridden keyword arguments."""
    defaults: dict[str, object] = {"document_type": "invoice"}
    defaults.update(kwargs)
    return InvoiceExtraction(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Cases that should NOT produce a finding (valid invoice document type)
# ---------------------------------------------------------------------------


def test_no_finding_when_document_type_is_invoice() -> None:
    """A valid invoice with document_type='invoice' returns no findings."""
    invoice = _invoice(document_type="invoice")
    assert check_document_type(invoice) == []


def test_no_finding_for_fully_populated_invoice() -> None:
    """A fully populated invoice with line items and totals returns no document type findings."""
    invoice = _invoice(
        document_type="invoice",
        vendor_name="Acme Corp",
        invoice_number="INV-2026-001",
        invoice_date=date(2026, 8, 1),
        due_date=date(2026, 8, 31),
        currency="USD",
        subtotal=Decimal("100.00"),
        tax=Decimal("10.00"),
        total=Decimal("110.00"),
        line_items=[
            InvoiceLineItem(
                description="Consulting",
                quantity=Decimal(1),
                unit_price=Decimal("100.00"),
                total_price=Decimal("100.00"),
            )
        ],
    )
    assert check_document_type(invoice) == []


# ---------------------------------------------------------------------------
# Cases that SHOULD produce a finding (triggering paths)
# ---------------------------------------------------------------------------


def test_purchase_order_document_type_triggers_finding() -> None:
    """A document classified as 'purchase_order' returns an unsupported_document_type finding."""
    invoice = _invoice(document_type="purchase_order")
    findings = check_document_type(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "unsupported_document_type"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "document_type == 'invoice'"
    assert finding.observed_value == "purchase_order"
    assert finding.expected_value == "invoice"
    assert (
        finding.explanation
        == "The extracted document is classified as a purchase order, not an invoice."
    )
    assert finding.details == {"document_type": "purchase_order"}


def test_unknown_document_type_triggers_finding() -> None:
    """A document classified as 'unknown' returns an unsupported_document_type finding."""
    invoice = _invoice(document_type="unknown")
    findings = check_document_type(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "unsupported_document_type"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "document_type == 'invoice'"
    assert finding.observed_value == "unknown"
    assert finding.expected_value == "invoice"
    assert (
        finding.explanation
        == "The extracted document could not be identified as an invoice."
    )
    assert finding.details == {"document_type": "unknown"}


def test_purchase_order_with_valid_amounts_and_vendor_still_triggers_finding() -> None:
    """Even if a purchase order has balanced amounts and known vendor, it cannot be cleared as an invoice."""
    invoice = _invoice(
        document_type="purchase_order",
        vendor_name="Acme Corp",
        purchase_order_number="PO-9999",
        invoice_date=date(2026, 8, 1),
        currency="USD",
        subtotal=Decimal("500.00"),
        total=Decimal("500.00"),
    )
    findings = check_document_type(invoice)

    assert len(findings) == 1
    assert findings[0].finding_type == "unsupported_document_type"
    assert findings[0].severity == "high"
    assert findings[0].observed_value == "purchase_order"


def test_unexpected_document_type_triggers_finding() -> None:
    """An unexpected document type string triggers unsupported_document_type with custom explanation."""
    invoice = InvoiceExtraction.model_construct(document_type="credit_note")
    findings = check_document_type(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "unsupported_document_type"
    assert finding.severity == "high"
    assert finding.observed_value == "credit_note"
    assert (
        finding.explanation
        == "The extracted document type 'credit_note' is not supported as an invoice."
    )
    assert finding.details == {"document_type": "credit_note"}


def test_check_document_type_preserves_invoice_immutability() -> None:
    """Verifies that check_document_type does not mutate the input InvoiceExtraction object."""
    invoice = _invoice(
        document_type="purchase_order",
        vendor_name="Acme Corp",
        invoice_number="INV-2026-001",
        invoice_date=date(2026, 8, 1),
        total=Decimal("500.00"),
    )
    original_dump = invoice.model_dump()
    _ = check_document_type(invoice)
    assert invoice.model_dump() == original_dump


# ---------------------------------------------------------------------------
# VerificationService and Verdict Integration Tests
# ---------------------------------------------------------------------------


class _FakeInvoiceRepository:
    """Minimal fake repository for VerificationService integration tests."""

    def list_vendor_invoices(self, vendor_key: str) -> list[object]:
        return []

    def get_purchase_order(self, vendor_key: str, po_number: str) -> object | None:
        return None


def test_verification_service_includes_unsupported_document_type() -> None:
    """VerificationService.verify must execute check_document_type and include its findings."""
    from veridoc.processing.verdict import derive_verdict
    from veridoc.verification.service import VerificationService

    invoice = _invoice(
        document_type="purchase_order",
        total=Decimal("500.00"),
        currency="USD",
    )
    service = VerificationService(repository=_FakeInvoiceRepository())  # type: ignore[arg-type]

    result = service.verify(invoice)

    types = [finding.finding_type for finding in result.findings]
    assert "unsupported_document_type" in types

    verdict = derive_verdict(result)
    assert verdict.status == "review_required"
    assert verdict.highest_severity == "high"


def test_verification_service_routes_unknown_document_to_review_required() -> None:
    """VerificationService.verify and derive_verdict route unknown documents to review_required with high severity."""
    from veridoc.processing.verdict import derive_verdict
    from veridoc.verification.service import VerificationService

    invoice = _invoice(
        document_type="unknown",
        total=Decimal("150.00"),
        currency="USD",
    )
    service = VerificationService(repository=_FakeInvoiceRepository())  # type: ignore[arg-type]

    result = service.verify(invoice)

    types = [finding.finding_type for finding in result.findings]
    assert "unsupported_document_type" in types

    verdict = derive_verdict(result)
    assert verdict.status == "review_required"
    assert verdict.highest_severity == "high"
