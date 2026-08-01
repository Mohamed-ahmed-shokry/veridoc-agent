"""FastAPI application construction tests."""

from fastapi import FastAPI

from veridoc.app import app


def test_application_object_imports_with_expected_metadata() -> None:
    """The installed package exposes a configured FastAPI application."""
    assert isinstance(app, FastAPI)
    assert app.title == "Veridoc"
    assert app.version == "0.1.0"
