"""Deterministic extraction uncertainty verification tests."""

from datetime import date
from decimal import Decimal

from veridoc.extraction.models import (
    ExtractionUncertainty,
    InvoiceExtraction,
    InvoiceLineItem,
)
from veridoc.verification.uncertainties import check_extraction_uncertainties


def _invoice(**kwargs: object) -> InvoiceExtraction:
    """Build an InvoiceExtraction with default or overridden keyword arguments."""
    defaults: dict[str, object] = {"document_type": "invoice"}
    defaults.update(kwargs)
    return InvoiceExtraction(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# Cases that should NOT produce a finding (no declared uncertainties)
# ---------------------------------------------------------------------------


def test_no_finding_when_uncertainties_empty() -> None:
    """An invoice with empty uncertainties returns no findings."""
    invoice = _invoice(uncertainties=[])
    assert check_extraction_uncertainties(invoice) == []


def test_no_finding_for_default_invoice() -> None:
    """A fully populated invoice without uncertainties returns no findings."""
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
    assert check_extraction_uncertainties(invoice) == []


# ---------------------------------------------------------------------------
# Cases that SHOULD produce a finding (triggering paths)
# ---------------------------------------------------------------------------


def test_single_uncertainty_with_field_triggers_finding() -> None:
    """An uncertainty on a specific field produces a structured finding."""
    reason = "Watermark obscures the last digit of the total."
    invoice = _invoice(
        total=Decimal("100.00"),
        uncertainties=[ExtractionUncertainty(field="total", reason=reason)],
    )
    findings = check_extraction_uncertainties(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "extraction_uncertainty"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "len(invoice.uncertainties) == 0"
    assert finding.observed_value == reason
    assert finding.expected_value is None
    assert (
        finding.explanation
        == f"Extraction uncertainty declared for field 'total': {reason}"
    )
    assert finding.details == {
        "field": "total",
        "reason": reason,
        "uncertainty_index": 0,
    }


def test_single_uncertainty_without_field_triggers_finding() -> None:
    """An uncertainty without a specific field produces a general uncertainty finding."""
    reason = "Page torn along bottom margin, some text may be missing."
    invoice = _invoice(
        uncertainties=[ExtractionUncertainty(field=None, reason=reason)],
    )
    findings = check_extraction_uncertainties(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "extraction_uncertainty"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "len(invoice.uncertainties) == 0"
    assert finding.observed_value == reason
    assert finding.expected_value is None
    assert finding.explanation == f"General extraction uncertainty declared: {reason}"
    assert finding.details == {
        "field": None,
        "reason": reason,
        "uncertainty_index": 0,
    }


def test_multiple_uncertainties_trigger_multiple_findings() -> None:
    """Multiple declared uncertainties produce one finding per uncertainty preserving order."""
    u0 = ExtractionUncertainty(field="invoice_date", reason="Date stamp smudged.")
    u1 = ExtractionUncertainty(field="tax", reason="Tax rate column header illegible.")
    u2 = ExtractionUncertainty(
        field=None, reason="Handwritten notes in margin partially illegible."
    )
    invoice = _invoice(uncertainties=[u0, u1, u2])
    findings = check_extraction_uncertainties(invoice)

    assert len(findings) == 3
    assert findings[0].finding_type == "extraction_uncertainty"
    assert findings[0].details["field"] == "invoice_date"
    assert findings[0].details["uncertainty_index"] == 0

    assert findings[1].finding_type == "extraction_uncertainty"
    assert findings[1].details["field"] == "tax"
    assert findings[1].details["uncertainty_index"] == 1

    assert findings[2].finding_type == "extraction_uncertainty"
    assert findings[2].details["field"] is None
    assert findings[2].details["uncertainty_index"] == 2


def test_check_extraction_uncertainties_preserves_immutability() -> None:
    """check_extraction_uncertainties does not mutate the input InvoiceExtraction."""
    invoice = _invoice(
        total=Decimal("500.00"),
        uncertainties=[
            ExtractionUncertainty(
                field="total", reason="Watermark partially obscures total."
            )
        ],
    )
    original_dump = invoice.model_dump()
    _ = check_extraction_uncertainties(invoice)
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


def test_verification_service_includes_extraction_uncertainty() -> None:
    """VerificationService.verify must execute check_extraction_uncertainties and include its findings."""
    from veridoc.processing.verdict import derive_verdict
    from veridoc.verification.service import VerificationService

    invoice = _invoice(
        total=Decimal("500.00"),
        currency="USD",
        uncertainties=[
            ExtractionUncertainty(
                field="total",
                reason="Watermark partially obscures total amount.",
            )
        ],
    )
    service = VerificationService(repository=_FakeInvoiceRepository())  # type: ignore[arg-type]

    result = service.verify(invoice)

    types = [finding.finding_type for finding in result.findings]
    assert "extraction_uncertainty" in types

    verdict = derive_verdict(result)
    assert verdict.status == "review_required"
    assert verdict.highest_severity == "medium"


def test_verification_service_routes_multiple_uncertainties_to_review_required() -> (
    None
):
    """VerificationService.verify and derive_verdict route invoices with multiple uncertainties to review_required."""
    from veridoc.processing.verdict import derive_verdict
    from veridoc.verification.service import VerificationService

    invoice = _invoice(
        total=Decimal("150.00"),
        currency="USD",
        uncertainties=[
            ExtractionUncertainty(
                field="due_date",
                reason="Due date text partially smudged.",
            ),
            ExtractionUncertainty(
                field=None,
                reason="General document fold across bottom text.",
            ),
        ],
    )
    service = VerificationService(repository=_FakeInvoiceRepository())  # type: ignore[arg-type]

    result = service.verify(invoice)

    findings = [
        f for f in result.findings if f.finding_type == "extraction_uncertainty"
    ]
    assert len(findings) == 2

    verdict = derive_verdict(result)
    assert verdict.status == "review_required"
    assert verdict.highest_severity == "medium"
