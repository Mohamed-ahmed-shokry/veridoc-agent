"""Smoke-test one installed Veridoc distribution."""

from importlib.metadata import distribution

import veridoc
from veridoc.__main__ import main as api_main
from veridoc.administration.cli import main as reference_main
from veridoc.app import app
from veridoc.review.persistence.cli import main as review_main

_EXPECTED_SCRIPTS = {
    "veridoc": "veridoc.__main__:main",
    "veridoc-reference": "veridoc.administration.cli:main",
    "veridoc-review": "veridoc.review.persistence.cli:main",
}
_REQUIRED_SCHEMA_PATHS = {
    "/health",
    "/ocr",
    "/extract",
    "/process",
    "/admin/reference-data/invoices",
    "/admin/reference-data/invoices/{record_id}",
    "/admin/reference-data/purchase-orders",
    "/admin/reference-data/purchase-orders/{record_id}",
    "/admin/reference-data/import",
}


def main() -> None:
    """Require installed metadata, entry points, and critical routes."""
    installed = distribution("veridoc")
    scripts = {
        entry_point.name: entry_point.value
        for entry_point in installed.entry_points
        if entry_point.group == "console_scripts"
    }
    schema_paths = set(app.openapi()["paths"])
    runtime_paths = {getattr(route, "path", None) for route in app.routes}

    assert installed.version == veridoc.__version__ == app.version
    assert scripts == _EXPECTED_SCRIPTS
    assert callable(api_main)
    assert callable(reference_main)
    assert callable(review_main)
    assert _REQUIRED_SCHEMA_PATHS <= schema_paths
    assert "/review" in runtime_paths


if __name__ == "__main__":
    main()
