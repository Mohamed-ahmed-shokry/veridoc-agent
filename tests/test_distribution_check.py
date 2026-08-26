"""Distribution archive safety-check tests."""

import stat
import tarfile
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from scripts.check_distribution import (
    _check_console_scripts,
    _check_member_paths,
    _check_source_member_types,
    _check_unique_member_paths,
    _check_wheel_member_types,
    _require_members,
    _required_package_members,
)
from scripts.smoke_distribution import (
    _REQUIRED_SCHEMA_PATHS,
    _collect_route_paths,
    api_main,
    reference_main,
    review_main,
)


@pytest.mark.parametrize(
    "member",
    [
        "../outside.txt",
        "/absolute.txt",
        "C:/outside.txt",
        "C:outside.txt",
        "veridoc\\..\\outside.txt",
        "veridoc/.env",
        "veridoc/.env.local",
        "veridoc/reference.sqlite3",
        "veridoc/private.key",
    ],
)
def test_distribution_check_rejects_unsafe_or_sensitive_members(member: str) -> None:
    with pytest.raises(RuntimeError):
        _check_member_paths([member])


def test_distribution_check_reports_missing_required_members() -> None:
    with pytest.raises(RuntimeError, match="missing required members"):
        _require_members(
            ["veridoc/app.py"],
            {"veridoc/__init__.py", "veridoc/app.py"},
            Path("dist/veridoc.whl"),
        )


@pytest.mark.parametrize(
    ("first", "second"),
    [
        ("veridoc/app.py", "veridoc/app.py"),
        ("veridoc/app.py", "VERIDOC/APP.PY"),
        ("veridoc/app.py", "veridoc/./app.py"),
        (
            "veridoc/caf\N{LATIN SMALL LETTER E WITH ACUTE}.py",
            "veridoc/cafe\N{COMBINING ACUTE ACCENT}.py",
        ),
    ],
)
def test_distribution_check_rejects_colliding_member_paths(
    first: str, second: str
) -> None:
    with pytest.raises(RuntimeError, match="colliding member paths"):
        _check_unique_member_paths([first, second])


def test_distribution_check_rejects_wheel_symlinks() -> None:
    member = zipfile.ZipInfo("veridoc/link")
    member.create_system = 3
    member.external_attr = (stat.S_IFLNK | 0o777) << 16

    with pytest.raises(RuntimeError, match="non-regular member"):
        _check_wheel_member_types([member], Path("dist/veridoc.whl"))


@pytest.mark.parametrize(
    "member_type", [tarfile.SYMTYPE, tarfile.LNKTYPE, tarfile.FIFOTYPE]
)
def test_distribution_check_rejects_special_source_members(
    member_type: bytes,
) -> None:
    member = tarfile.TarInfo("veridoc-0.1.0/link")
    member.type = member_type

    with pytest.raises(RuntimeError, match="non-regular member"):
        _check_source_member_types([member], Path("dist/veridoc.tar.gz"))


def test_distribution_check_requires_phase_8_runtime_boundaries() -> None:
    required = _required_package_members("veridoc")

    assert "veridoc/__main__.py" in required
    assert "veridoc/administration/api.py" in required
    assert "veridoc/administration/cli.py" in required
    assert "veridoc/persistence/migrations.py" in required
    assert "veridoc/persistence/maintenance.py" in required
    assert "veridoc/persistence/schema.py" in required


def test_distribution_check_requires_phase_9_runtime_boundaries() -> None:
    required = _required_package_members("veridoc")

    assert "veridoc/review/api.py" in required
    assert "veridoc/review/console_page.py" in required
    assert "veridoc/review/persistence/cli.py" in required
    assert "veridoc/review/persistence/maintenance.py" in required
    assert "veridoc/review/persistence/migrations.py" in required
    assert "veridoc/review/persistence/schema.py" in required
    assert "veridoc/review/persistence/sqlite.py" in required


def test_distribution_check_requires_all_console_scripts() -> None:
    valid = (
        b"[console_scripts]\n"
        b"veridoc = veridoc.__main__:main\n"
        b"veridoc-reference = veridoc.administration.cli:main\n"
        b"veridoc-review = veridoc.review.persistence.cli:main\n"
    )

    _check_console_scripts(valid, Path("dist/veridoc.whl"))

    with pytest.raises(RuntimeError, match="console scripts"):
        _check_console_scripts(
            b"[console_scripts]\nveridoc = veridoc.__main__:main\n",
            Path("dist/veridoc.whl"),
        )


def test_distribution_smoke_requires_all_administration_route_families() -> None:
    assert {
        "/admin/reference-data/invoices",
        "/admin/reference-data/invoices/{record_id}",
        "/admin/reference-data/purchase-orders",
        "/admin/reference-data/purchase-orders/{record_id}",
        "/admin/reference-data/import",
    } <= _REQUIRED_SCHEMA_PATHS


def test_collect_route_paths_finds_routes_behind_an_included_router_wrapper() -> None:
    # Depending on the installed Starlette version, app.include_router(...)
    # can appear in app.routes either as a flattened APIRoute, a Mount-style
    # object exposing .routes, or an opaque wrapper exposing its routes only
    # through .original_router.routes (observed with starlette 1.6.0) — all
    # three must be discoverable.
    routes = [
        SimpleNamespace(path="/health", routes=None, original_router=None),
        SimpleNamespace(
            path=None,
            routes=[
                SimpleNamespace(path="/admin/x", routes=None, original_router=None)
            ],
            original_router=None,
        ),
        SimpleNamespace(
            path=None,
            routes=None,
            original_router=SimpleNamespace(
                routes=[
                    SimpleNamespace(
                        path="/review/console", routes=None, original_router=None
                    )
                ]
            ),
        ),
    ]

    assert _collect_route_paths(routes) == {"/health", "/admin/x", "/review/console"}


def test_distribution_smoke_requires_all_review_route_families() -> None:
    assert {
        "/review/session",
        "/review/cases",
        "/review/cases/{case_id}",
        "/review/cases/{case_id}/assignment",
        "/review/cases/{case_id}/escalations",
        "/review/cases/{case_id}/decisions",
    } <= _REQUIRED_SCHEMA_PATHS


def test_distribution_smoke_imports_all_console_targets() -> None:
    assert callable(api_main)
    assert callable(reference_main)
    assert callable(review_main)
