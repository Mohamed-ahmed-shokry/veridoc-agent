"""Deterministic non-positive invoice total detection tests.

The non-positive invoice total check fires whenever an extracted invoice total
is present and non-positive (<= 0). It flags zero-amount invoices (medium
severity) to catch pro-forma quotes, zero-value vouchers, or OCR extraction
failures, and negative-amount invoices (high severity) to catch credit memos,
refunds, or billing reversals masquerading as commercial invoices.
"""

from __future__ import annotations

from decimal import Decimal

from veridoc.extraction.models import InvoiceExtraction, InvoiceLineItem
from veridoc.persistence.protocol import InvoiceRepository
from veridoc.processing.verdict import derive_verdict
from veridoc.verification.invoice_totals import check_non_positive_invoice_total
from veridoc.verification.models import VerificationResult
from veridoc.verification.references import HistoricalInvoice, PurchaseOrder
from veridoc.verification.service import VerificationService


def _invoice(**kwargs: object) -> InvoiceExtraction:
    """Build a minimal InvoiceExtraction with overridable keyword arguments."""
    defaults: dict[str, object] = {"document_type": "invoice"}
    defaults.update(kwargs)
    return InvoiceExtraction(**defaults)  # type: ignore[arg-type]


class _StubRepository(InvoiceRepository):
    """Minimal repository stub for verification service tests."""

    def list_vendor_invoices(self, vendor_key: str) -> list[HistoricalInvoice]:
        return []

    def get_purchase_order(
        self, vendor_key: str, purchase_order_number: str
    ) -> PurchaseOrder | None:
        return None


# ---------------------------------------------------------------------------
# Cases that should NOT produce a finding
# ---------------------------------------------------------------------------


def test_no_finding_when_total_is_absent() -> None:
    invoice = _invoice(total=None)
    assert check_non_positive_invoice_total(invoice) == []


def test_no_finding_when_total_is_positive() -> None:
    invoice = _invoice(total="100.00")
    assert check_non_positive_invoice_total(invoice) == []


def test_no_finding_when_total_is_minimal_positive() -> None:
    invoice = _invoice(total="0.01")
    assert check_non_positive_invoice_total(invoice) == []


def test_no_finding_when_total_is_micro_positive() -> None:
    invoice = _invoice(total="0.000001")
    assert check_non_positive_invoice_total(invoice) == []


def test_no_finding_when_total_is_large_positive() -> None:
    invoice = _invoice(total="999999999.99")
    assert check_non_positive_invoice_total(invoice) == []


def test_no_finding_when_total_is_positive_integer_string() -> None:
    invoice = _invoice(total="500")
    assert check_non_positive_invoice_total(invoice) == []


def test_no_finding_when_total_is_positive_decimal() -> None:
    invoice = _invoice(total=Decimal("250.50"))
    assert check_non_positive_invoice_total(invoice) == []


# ---------------------------------------------------------------------------
# Zero total cases (SHOULD produce medium-severity finding)
# ---------------------------------------------------------------------------


def test_finding_produced_when_total_is_zero() -> None:
    invoice = _invoice(total="0.00")
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_invoice_total"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.total > 0"
    assert finding.observed_value == "0.00"
    assert finding.expected_value == "> 0.00"
    assert finding.details == {
        "field": "total",
        "total": "0.00",
        "is_zero": True,
        "is_negative": False,
    }


def test_finding_produced_when_total_is_integer_zero() -> None:
    invoice = _invoice(total="0")
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_invoice_total"
    assert finding.severity == "medium"
    assert finding.details["is_zero"] is True
    assert finding.details["is_negative"] is False


def test_finding_produced_when_total_is_multi_decimal_zero() -> None:
    invoice = _invoice(total="0.000000")
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_invoice_total"
    assert finding.severity == "medium"
    assert finding.details["is_zero"] is True
    assert finding.details["is_negative"] is False


def test_finding_produced_when_total_is_decimal_zero() -> None:
    invoice = _invoice(total=Decimal("0.00"))
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_invoice_total"
    assert finding.severity == "medium"
    assert finding.details["is_zero"] is True
    assert finding.details["is_negative"] is False


def test_zero_total_finding_includes_currency_when_present() -> None:
    invoice = _invoice(total="0.00", currency="USD")
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    assert findings[0].details["currency"] == "USD"


def test_zero_total_explanation_text() -> None:
    invoice = _invoice(total="0.00")
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    assert "zero" in findings[0].explanation.lower()
    assert (
        "pro-forma" in findings[0].explanation.lower()
        or "voucher" in findings[0].explanation.lower()
    )


# ---------------------------------------------------------------------------
# Negative total cases (SHOULD produce high-severity finding)
# ---------------------------------------------------------------------------


def test_finding_produced_when_total_is_negative() -> None:
    invoice = _invoice(total="-100.00")
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_invoice_total"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.total > 0"
    assert finding.observed_value == "-100.00"
    assert finding.expected_value == "> 0.00"
    assert finding.details == {
        "field": "total",
        "total": "-100.00",
        "is_zero": False,
        "is_negative": True,
    }


def test_finding_produced_when_total_is_minimal_negative() -> None:
    invoice = _invoice(total="-0.01")
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_invoice_total"
    assert finding.severity == "high"
    assert finding.details["is_zero"] is False
    assert finding.details["is_negative"] is True


def test_finding_produced_when_total_is_micro_negative() -> None:
    invoice = _invoice(total="-0.000001")
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_invoice_total"
    assert finding.severity == "high"
    assert finding.details["is_zero"] is False
    assert finding.details["is_negative"] is True


def test_finding_produced_when_total_is_large_negative() -> None:
    invoice = _invoice(total="-999999.99")
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_invoice_total"
    assert finding.severity == "high"
    assert finding.details["is_zero"] is False
    assert finding.details["is_negative"] is True


def test_negative_total_finding_includes_currency_when_present() -> None:
    invoice = _invoice(total="-50.00", currency="EUR")
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    assert findings[0].details["currency"] == "EUR"


def test_negative_total_explanation_text() -> None:
    invoice = _invoice(total="-100.00")
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    assert "negative" in findings[0].explanation.lower()
    assert (
        "credit note" in findings[0].explanation.lower()
        or "refund" in findings[0].explanation.lower()
    )


def test_negative_zero_evaluates_as_zero() -> None:
    invoice = _invoice(total=Decimal("-0.00"))
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.severity == "medium"
    assert finding.details["is_zero"] is True
    assert finding.details["is_negative"] is False


# ---------------------------------------------------------------------------
# Orthogonality and Immutability
# ---------------------------------------------------------------------------


def test_non_positive_total_independent_of_purchase_order() -> None:
    invoice = _invoice(total="0.00", purchase_order_number="PO-12345")
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    assert findings[0].finding_type == "non_positive_invoice_total"


def test_non_positive_total_independent_of_line_items() -> None:
    invoice = _invoice(
        total="-50.00",
        line_items=[
            InvoiceLineItem(
                product_identifier="ITEM-1",
                quantity=Decimal(1),
                unit_price=Decimal("50.00"),
                total_price=Decimal("50.00"),
            )
        ],
    )
    findings = check_non_positive_invoice_total(invoice)

    assert len(findings) == 1
    assert findings[0].finding_type == "non_positive_invoice_total"
    assert findings[0].severity == "high"


def test_non_positive_invoice_total_immutability() -> None:
    invoice = _invoice(total="0.00", currency="USD")
    original_dict = invoice.model_dump()

    check_non_positive_invoice_total(invoice)

    assert invoice.model_dump() == original_dict


# ---------------------------------------------------------------------------
# VerificationService and ProcessingVerdict integration
# ---------------------------------------------------------------------------


def test_verification_service_includes_zero_total_finding() -> None:
    service = VerificationService(_StubRepository())
    invoice = _invoice(
        vendor_name="Acme Corp",
        invoice_number="INV-2026-001",
        total="0.00",
        currency="USD",
    )

    result = service.verify(invoice)
    finding_types = [f.finding_type for f in result.findings]

    assert "non_positive_invoice_total" in finding_types
    zero_finding = next(
        f for f in result.findings if f.finding_type == "non_positive_invoice_total"
    )
    assert zero_finding.severity == "medium"


def test_verification_service_includes_negative_total_finding() -> None:
    service = VerificationService(_StubRepository())
    invoice = _invoice(
        vendor_name="Acme Corp",
        invoice_number="INV-2026-002",
        total="-250.00",
        currency="USD",
    )

    result = service.verify(invoice)
    finding_types = [f.finding_type for f in result.findings]

    assert "non_positive_invoice_total" in finding_types
    neg_finding = next(
        f for f in result.findings if f.finding_type == "non_positive_invoice_total"
    )
    assert neg_finding.severity == "high"


def test_verification_service_returns_no_finding_for_positive_total() -> None:
    service = VerificationService(_StubRepository())
    invoice = _invoice(
        vendor_name="Acme Corp",
        invoice_number="INV-2026-003",
        total="250.00",
        currency="USD",
    )

    result = service.verify(invoice)
    finding_types = [f.finding_type for f in result.findings]

    assert "non_positive_invoice_total" not in finding_types


def test_derive_verdict_medium_severity_for_zero_total() -> None:
    invoice = _invoice(total="0.00")
    findings = check_non_positive_invoice_total(invoice)
    verdict = derive_verdict(VerificationResult(findings=findings))

    assert verdict.status == "review_required"
    assert verdict.highest_severity == "medium"
    assert verdict.finding_count == 1


def test_derive_verdict_high_severity_for_negative_total() -> None:
    invoice = _invoice(total="-100.00")
    findings = check_non_positive_invoice_total(invoice)
    verdict = derive_verdict(VerificationResult(findings=findings))

    assert verdict.status == "review_required"
    assert verdict.highest_severity == "high"
    assert verdict.finding_count == 1
