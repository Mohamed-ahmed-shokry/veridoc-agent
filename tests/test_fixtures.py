"""Synthetic fixture determinism tests."""

from tests.fixtures import fictional_invoice_pdf, fictional_invoice_png


def test_fictional_invoice_fixtures_are_deterministic() -> None:
    assert fictional_invoice_png() == fictional_invoice_png()
    assert fictional_invoice_pdf(2) == fictional_invoice_pdf(2)
