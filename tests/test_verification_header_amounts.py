"""Deterministic invoice header monetary bound tests.

Covers ``check_non_positive_subtotal``, ``check_negative_tax``,
``check_invalid_discount``, and ``check_header_amounts`` in
``veridoc.verification.header_amounts``, plus ``VerificationService``,
``ExplanationService``, and ``derive_verdict`` integration.
"""

from __future__ import annotations

from decimal import Decimal

from veridoc.explanation.fallback import render_deterministic_explanations
from veridoc.extraction.models import InvoiceExtraction
from veridoc.persistence.protocol import InvoiceRepository
from veridoc.processing.verdict import derive_verdict
from veridoc.verification.header_amounts import (
    check_header_amounts,
    check_invalid_discount,
    check_negative_tax,
    check_non_positive_subtotal,
)
from veridoc.verification.models import VerificationResult
from veridoc.verification.references import HistoricalInvoice, PurchaseOrder
from veridoc.verification.service import VerificationService


def _invoice(**kwargs: object) -> InvoiceExtraction:
    """Build a minimal InvoiceExtraction with overridable keyword arguments."""
    defaults: dict[str, object] = {"document_type": "invoice"}
    defaults.update(kwargs)
    return InvoiceExtraction(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# check_non_positive_subtotal: non-triggering paths
# ---------------------------------------------------------------------------


def test_subtotal_no_finding_when_absent() -> None:
    invoice = _invoice(subtotal=None)
    assert check_non_positive_subtotal(invoice) == []


def test_subtotal_no_finding_when_positive() -> None:
    invoice = _invoice(subtotal="100.00")
    assert check_non_positive_subtotal(invoice) == []


def test_subtotal_no_finding_when_minimal_positive() -> None:
    invoice = _invoice(subtotal="0.01")
    assert check_non_positive_subtotal(invoice) == []


def test_subtotal_no_finding_when_micro_positive() -> None:
    invoice = _invoice(subtotal="0.000001")
    assert check_non_positive_subtotal(invoice) == []


def test_subtotal_no_finding_when_large_positive() -> None:
    invoice = _invoice(subtotal="999999999.99")
    assert check_non_positive_subtotal(invoice) == []


# ---------------------------------------------------------------------------
# check_non_positive_subtotal: zero subtotal (medium severity)
# ---------------------------------------------------------------------------


def test_subtotal_finding_when_zero() -> None:
    invoice = _invoice(subtotal="0.00")
    findings = check_non_positive_subtotal(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_subtotal"
    assert finding.severity == "medium"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.subtotal > 0"
    assert finding.observed_value == "0.00"
    assert finding.expected_value == "> 0.00"
    assert "zero" in finding.explanation.lower()
    assert finding.details == {
        "field": "subtotal",
        "subtotal": "0.00",
        "is_zero": True,
        "is_negative": False,
    }


def test_subtotal_finding_when_zero_across_representations() -> None:
    for raw in ("0", "0.000000", Decimal(0), Decimal("-0.00")):
        invoice = _invoice(subtotal=raw)
        findings = check_non_positive_subtotal(invoice)
        assert len(findings) == 1
        assert findings[0].finding_type == "non_positive_subtotal"
        assert findings[0].severity == "medium"
        assert findings[0].details["is_zero"] is True
        assert findings[0].details["is_negative"] is False


def test_subtotal_zero_includes_currency_when_present() -> None:
    invoice = _invoice(subtotal="0.00", currency="USD")
    findings = check_non_positive_subtotal(invoice)

    assert len(findings) == 1
    assert findings[0].details["currency"] == "USD"


# ---------------------------------------------------------------------------
# check_non_positive_subtotal: negative subtotal (high severity)
# ---------------------------------------------------------------------------


def test_subtotal_finding_when_negative() -> None:
    invoice = _invoice(subtotal="-150.00")
    findings = check_non_positive_subtotal(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "non_positive_subtotal"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.subtotal > 0"
    assert finding.observed_value == "-150.00"
    assert finding.expected_value == "> 0.00"
    assert "negative" in finding.explanation.lower()
    assert finding.details == {
        "field": "subtotal",
        "subtotal": "-150.00",
        "is_zero": False,
        "is_negative": True,
    }


def test_subtotal_finding_when_minimal_and_micro_negative() -> None:
    for raw in ("-0.01", "-0.000001", "-999999.99"):
        invoice = _invoice(subtotal=raw)
        findings = check_non_positive_subtotal(invoice)
        assert len(findings) == 1
        assert findings[0].severity == "high"
        assert findings[0].details["is_negative"] is True
        assert findings[0].details["is_zero"] is False


def test_subtotal_negative_includes_currency_when_present() -> None:
    invoice = _invoice(subtotal="-75.00", currency="EUR")
    findings = check_non_positive_subtotal(invoice)

    assert len(findings) == 1
    assert findings[0].details["currency"] == "EUR"


# ---------------------------------------------------------------------------
# check_negative_tax: non-triggering and triggering paths
# ---------------------------------------------------------------------------


def test_tax_no_finding_when_absent() -> None:
    invoice = _invoice(tax=None)
    assert check_negative_tax(invoice) == []


def test_tax_no_finding_when_zero() -> None:
    for raw in ("0", "0.00", "0.000000", Decimal(0), Decimal("-0.00")):
        invoice = _invoice(tax=raw)
        assert check_negative_tax(invoice) == []


def test_tax_no_finding_when_positive() -> None:
    for raw in ("0.01", "0.000001", "15.00", "999999.99"):
        invoice = _invoice(tax=raw)
        assert check_negative_tax(invoice) == []


def test_tax_finding_when_negative() -> None:
    invoice = _invoice(tax="-15.00")
    findings = check_negative_tax(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "negative_tax"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.tax >= 0"
    assert finding.observed_value == "-15.00"
    assert finding.expected_value == ">= 0.00"
    assert "negative" in finding.explanation.lower()
    assert finding.details == {
        "field": "tax",
        "tax": "-15.00",
        "is_negative": True,
    }


def test_tax_finding_when_minimal_and_micro_negative() -> None:
    for raw in ("-0.01", "-0.000001", "-50000.00"):
        invoice = _invoice(tax=raw)
        findings = check_negative_tax(invoice)
        assert len(findings) == 1
        assert findings[0].finding_type == "negative_tax"
        assert findings[0].severity == "high"


def test_tax_negative_includes_currency_when_present() -> None:
    invoice = _invoice(tax="-12.50", currency="GBP")
    findings = check_negative_tax(invoice)

    assert len(findings) == 1
    assert findings[0].details["currency"] == "GBP"


# ---------------------------------------------------------------------------
# check_invalid_discount: negative discount tests
# ---------------------------------------------------------------------------


def test_discount_no_finding_when_absent() -> None:
    invoice = _invoice(discount=None)
    assert check_invalid_discount(invoice) == []


def test_discount_no_finding_when_zero() -> None:
    for raw in ("0", "0.00", "0.000000", Decimal(0), Decimal("-0.00")):
        invoice = _invoice(discount=raw)
        assert check_invalid_discount(invoice) == []


def test_discount_finding_when_negative() -> None:
    invoice = _invoice(discount="-10.00")
    findings = check_invalid_discount(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_discount"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.discount >= 0"
    assert finding.observed_value == "-10.00"
    assert finding.expected_value == ">= 0.00"
    assert "negative" in finding.explanation.lower()
    assert finding.details == {
        "field": "discount",
        "discount": "-10.00",
        "reason": "negative_discount",
        "is_negative": True,
    }


def test_discount_finding_when_minimal_and_micro_negative() -> None:
    for raw in ("-0.01", "-0.000001", "-25000.00"):
        invoice = _invoice(discount=raw)
        findings = check_invalid_discount(invoice)
        assert len(findings) == 1
        assert findings[0].finding_type == "invalid_discount"
        assert findings[0].severity == "high"
        assert findings[0].details["reason"] == "negative_discount"


def test_discount_negative_includes_currency_when_present() -> None:
    invoice = _invoice(discount="-5.00", currency="USD")
    findings = check_invalid_discount(invoice)

    assert len(findings) == 1
    assert findings[0].details["currency"] == "USD"


# ---------------------------------------------------------------------------
# check_invalid_discount: discount exceeding subtotal tests
# ---------------------------------------------------------------------------


def test_discount_no_finding_when_less_than_subtotal() -> None:
    invoice = _invoice(subtotal="100.00", discount="20.00")
    assert check_invalid_discount(invoice) == []


def test_discount_no_finding_when_equal_to_subtotal() -> None:
    invoice = _invoice(subtotal="100.00", discount="100.00")
    assert check_invalid_discount(invoice) == []


def test_discount_no_finding_when_subtotal_is_absent() -> None:
    invoice = _invoice(subtotal=None, discount="50.00")
    assert check_invalid_discount(invoice) == []


def test_discount_exceeding_subtotal_ignored_when_subtotal_is_zero_or_negative() -> (
    None
):
    for raw_subtotal in ("0.00", "-50.00"):
        invoice = _invoice(subtotal=raw_subtotal, discount="10.00")
        assert check_invalid_discount(invoice) == []


def test_discount_finding_when_exceeds_subtotal() -> None:
    invoice = _invoice(subtotal="100.00", discount="125.00")
    findings = check_invalid_discount(invoice)

    assert len(findings) == 1
    finding = findings[0]
    assert finding.finding_type == "invalid_discount"
    assert finding.severity == "high"
    assert finding.comparison_source == "invoice_fields"
    assert finding.deterministic_rule == "invoice.discount <= invoice.subtotal"
    assert finding.observed_value == "125.00"
    assert finding.expected_value == "<= 100.00"
    assert "exceeds" in finding.explanation.lower()
    assert finding.details == {
        "field": "discount",
        "discount": "125.00",
        "subtotal": "100.00",
        "reason": "discount_exceeds_subtotal",
        "is_negative": False,
    }


def test_discount_finding_when_slightly_exceeds_subtotal() -> None:
    invoice = _invoice(subtotal="100.00", discount="100.01")
    findings = check_invalid_discount(invoice)

    assert len(findings) == 1
    assert findings[0].finding_type == "invalid_discount"
    assert findings[0].severity == "high"
    assert findings[0].details["reason"] == "discount_exceeds_subtotal"


def test_discount_finding_when_massively_exceeds_subtotal() -> None:
    invoice = _invoice(subtotal="50.00", discount="5000.00", currency="EUR")
    findings = check_invalid_discount(invoice)

    assert len(findings) == 1
    assert findings[0].details["currency"] == "EUR"
    assert findings[0].details["subtotal"] == "50.00"
    assert findings[0].details["discount"] == "5000.00"


# ---------------------------------------------------------------------------
# check_header_amounts: composition and immutability tests
# ---------------------------------------------------------------------------


def test_header_amounts_clean_invoice_produces_no_findings() -> None:
    invoice = _invoice(
        subtotal="200.00",
        tax="40.00",
        discount="20.00",
        total="220.00",
    )
    assert check_header_amounts(invoice) == []


def test_header_amounts_clean_with_zero_tax_and_zero_discount() -> None:
    invoice = _invoice(
        subtotal="100.00",
        tax="0.00",
        discount="0.00",
        total="100.00",
    )
    assert check_header_amounts(invoice) == []


def test_header_amounts_clean_with_all_none() -> None:
    invoice = _invoice(subtotal=None, tax=None, discount=None, total=None)
    assert check_header_amounts(invoice) == []


def test_header_amounts_composes_multiple_violations_in_deterministic_order() -> None:
    invoice = _invoice(
        subtotal="-100.00",
        tax="-20.00",
        discount="-10.00",
        total="0.00",
    )
    findings = check_header_amounts(invoice)

    assert len(findings) == 3
    assert [f.finding_type for f in findings] == [
        "non_positive_subtotal",
        "negative_tax",
        "invalid_discount",
    ]
    assert all(f.severity == "high" for f in findings)


def test_header_amounts_composes_zero_subtotal_and_exceeding_discount() -> None:
    invoice = _invoice(
        subtotal="0.00",
        tax="10.00",
        discount="-5.00",
    )
    findings = check_header_amounts(invoice)

    assert len(findings) == 2
    assert findings[0].finding_type == "non_positive_subtotal"
    assert findings[0].severity == "medium"
    assert findings[1].finding_type == "invalid_discount"
    assert findings[1].severity == "high"


def test_header_amounts_input_immutability() -> None:
    invoice = _invoice(
        subtotal="-50.00",
        tax="-10.00",
        discount="75.00",
        currency="USD",
    )
    original_dict = invoice.model_dump()

    check_header_amounts(invoice)

    assert invoice.model_dump() == original_dict


# ---------------------------------------------------------------------------
# VerificationService, verdict derivation, and explanation integration tests
# ---------------------------------------------------------------------------


class _StubRepository(InvoiceRepository):
    """Minimal repository stub for verification service tests."""

    def list_vendor_invoices(self, vendor_key: str) -> list[HistoricalInvoice]:
        return []

    def get_purchase_order(
        self, vendor_key: str, purchase_order_number: str
    ) -> PurchaseOrder | None:
        return None


def test_verification_service_integrates_header_amount_findings() -> None:
    invoice = _invoice(
        vendor_name="Acme Corp",
        invoice_number="INV-HDR-1",
        subtotal="-100.00",
        tax="-20.00",
        discount="-5.00",
        total="0.00",
    )
    service = VerificationService(repository=_StubRepository())
    result = service.verify(invoice)

    finding_types = [f.finding_type for f in result.findings]
    assert "non_positive_subtotal" in finding_types
    assert "negative_tax" in finding_types
    assert "invalid_discount" in finding_types


def test_verdict_derivation_drives_review_required_for_negative_subtotal() -> None:
    findings = check_non_positive_subtotal(_invoice(subtotal="-100.00"))
    assert len(findings) == 1
    verdict = derive_verdict(VerificationResult(findings=findings))

    assert verdict.status == "review_required"
    assert verdict.highest_severity == "high"
    assert verdict.finding_count == 1
    assert "1 deterministic verification finding requires review" in verdict.summary


def test_verdict_derivation_drives_review_required_for_zero_subtotal() -> None:
    findings = check_non_positive_subtotal(_invoice(subtotal="0.00"))
    assert len(findings) == 1
    verdict = derive_verdict(VerificationResult(findings=findings))

    assert verdict.status == "review_required"
    assert verdict.highest_severity == "medium"
    assert verdict.finding_count == 1


def test_verdict_derivation_drives_review_required_for_negative_tax() -> None:
    findings = check_negative_tax(_invoice(tax="-15.00"))
    assert len(findings) == 1
    verdict = derive_verdict(VerificationResult(findings=findings))

    assert verdict.status == "review_required"
    assert verdict.highest_severity == "high"
    assert verdict.finding_count == 1


def test_verdict_derivation_drives_review_required_for_invalid_discount() -> None:
    findings = check_invalid_discount(_invoice(subtotal="100.00", discount="150.00"))
    assert len(findings) == 1
    verdict = derive_verdict(VerificationResult(findings=findings))

    assert verdict.status == "review_required"
    assert verdict.highest_severity == "high"
    assert verdict.finding_count == 1


def test_deterministic_explanation_rendering_for_header_amount_findings() -> None:
    findings = check_header_amounts(
        _invoice(subtotal="-50.00", tax="-10.00", discount="-5.00")
    )
    explanation_result = render_deterministic_explanations(
        VerificationResult(findings=findings)
    )

    assert len(explanation_result.explanations) == 3
    narratives = [e.narrative for e in explanation_result.explanations]
    assert any("invoice.subtotal > 0" in n for n in narratives)
    assert any("invoice.tax >= 0" in n for n in narratives)
    assert any("invoice.discount >= 0" in n for n in narratives)
    assert all(e.source == "deterministic" for e in explanation_result.explanations)
