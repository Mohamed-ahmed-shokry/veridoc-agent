"""Deterministic document type verification for extracted documents.

In commercial accounts payable (AP) workflows, documents submitted for invoice
processing must be genuine payable invoices. Veridoc's structured extraction
boundary classifies documents into ``document_type``: ``"invoice"``,
``"purchase_order"``, or ``"unknown"``.

Ingesting a purchase order or an unknown document (such as a quote, packing slip,
receipt, or non-commercial page) into the invoice reconciliation pipeline introduces
critical operational and financial risks:
1. An internal purchase order could be mistakenly approved for disbursement, causing
   unauthorized funds transfer or double payment when the actual vendor invoice arrives.
2. An unclassified or unknown document could pollute AP registers with false liabilities.

Establishing an explicit, deterministic document type check ensures that only genuine
invoices (``document_type == "invoice"``) can clear automated processing. Any non-invoice
document is immediately flagged with high severity (``unsupported_document_type``)
requiring human review.
"""

from __future__ import annotations

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationFinding


def check_document_type(
    invoice: InvoiceExtraction,
) -> list[VerificationFinding]:
    """Flag extracted documents that are not payable invoices.

    Returns an empty list when:
    - ``invoice.document_type == "invoice"``.

    Returns a list with one ``unsupported_document_type`` finding (severity="high")
    when ``invoice.document_type != "invoice"`` (such as ``"purchase_order"`` or
    ``"unknown"``).
    """
    doc_type = invoice.document_type
    if doc_type == "invoice":
        return []

    if doc_type == "purchase_order":
        explanation = (
            "The extracted document is classified as a purchase order, not an invoice."
        )
    elif doc_type == "unknown":
        explanation = "The extracted document could not be identified as an invoice."
    else:
        explanation = (
            f"The extracted document type '{doc_type}' is not supported as an invoice."
        )

    return [
        VerificationFinding(
            finding_type="unsupported_document_type",
            severity="high",
            explanation=explanation,
            comparison_source="invoice_fields",
            deterministic_rule="document_type == 'invoice'",
            observed_value=str(doc_type),
            expected_value="invoice",
            details={"document_type": str(doc_type)},
        )
    ]


__all__ = ["check_document_type"]
