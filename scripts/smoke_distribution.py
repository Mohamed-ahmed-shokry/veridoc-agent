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
    "/review/session",
    "/review/cases",
    "/review/cases/{case_id}",
    "/review/cases/{case_id}/assignment",
    "/review/cases/{case_id}/escalations",
    "/review/cases/{case_id}/decisions",
}


def _collect_route_paths(routes: object) -> set[str]:
    """Return every route path reachable from ``routes``, however nested.

    ``app.include_router(...)`` does not always flatten sub-routes directly
    into ``app.routes``: depending on the installed Starlette version, an
    included router can appear as an opaque wrapper exposing its routes only
    through ``original_router.routes`` rather than as top-level ``APIRoute``
    entries. Walking both ``route.routes`` and ``route.original_router.routes``
    keeps this correct across that representation difference.
    """
    paths: set[str] = set()
    for route in routes:  # type: ignore[attr-defined]
        path = getattr(route, "path", None)
        if path:
            paths.add(path)
        nested = getattr(route, "routes", None)
        if nested:
            paths |= _collect_route_paths(nested)
        original_router = getattr(route, "original_router", None)
        if original_router is not None:
            paths |= _collect_route_paths(getattr(original_router, "routes", []))
    return paths


def main() -> None:
    """Require installed metadata, entry points, and critical routes."""
    installed = distribution("veridoc")
    scripts = {
        entry_point.name: entry_point.value
        for entry_point in installed.entry_points
        if entry_point.group == "console_scripts"
    }
    schema_paths = set(app.openapi()["paths"])
    runtime_paths = _collect_route_paths(app.routes)

    assert installed.version == veridoc.__version__ == app.version
    assert scripts == _EXPECTED_SCRIPTS
    assert callable(api_main)
    assert callable(reference_main)
    assert callable(review_main)
    assert _REQUIRED_SCHEMA_PATHS <= schema_paths
    assert "/review" in runtime_paths
    assert "/review/console" in runtime_paths


if __name__ == "__main__":
    main()
