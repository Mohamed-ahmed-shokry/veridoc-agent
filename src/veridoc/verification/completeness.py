"""Deterministic required-field completeness verification for invoices.

Every other verification rule is conditional on the fields it evaluates. A
sparse extraction can therefore pass arithmetic, date, purchase-order, and
historical checks vacuously and receive an unearned ``clear`` verdict even
though the facts required for accounts-payable posting are absent.

This module requires the four invoice fields that identity, date, and money
rules depend on: ``invoice_number``, ``invoice_date``, ``currency``, and
``total``. Vendor identity is excluded because it already produces a dedicated
``insufficient_history`` finding, and optional commercial fields such as
``due_date``, ``payment_terms``, ``subtotal``, ``tax``, ``discount``, and line
items are excluded because many legitimate invoices omit them.
"""

from __future__ import annotations

from typing import Final, NamedTuple

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import FindingSeverity, VerificationFinding


class RequiredInvoiceField(NamedTuple):
    """One required invoice field, its severity, and its verification role."""

    name: str
    severity: FindingSeverity
    description: str


REQUIRED_INVOICE_FIELDS: Final[tuple[RequiredInvoiceField, ...]] = (
    RequiredInvoiceField(
        name="invoice_number",
        severity="high",
        description="vendor-scoped invoice identity",
    ),
    RequiredInvoiceField(
        name="invoice_date",
        severity="medium",
        description="invoice issue date",
    ),
    RequiredInvoiceField(
        name="currency",
        severity="medium",
        description="ISO 4217 invoice currency",
    ),
    RequiredInvoiceField(
        name="total",
        severity="high",
        description="payable invoice total",
    ),
)


def check_required_fields(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Return one finding for each absent required invoice field."""
    findings: list[VerificationFinding] = []
    for required in REQUIRED_INVOICE_FIELDS:
        if getattr(invoice, required.name) is not None:
            continue
        findings.append(
            VerificationFinding(
                finding_type="missing_required_field",
                severity=required.severity,
                explanation=(
                    f"The required invoice field '{required.name}' is missing; "
                    f"{required.description} is required for verification."
                ),
                comparison_source="invoice_fields",
                deterministic_rule=f"invoice.{required.name} is not None",
                observed_value=None,
                expected_value=required.name,
                details={"field": required.name},
            )
        )
    return findings


__all__ = ["REQUIRED_INVOICE_FIELDS", "RequiredInvoiceField", "check_required_fields"]
