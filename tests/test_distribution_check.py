"""Distribution archive safety-check tests."""

from pathlib import Path

import pytest

from scripts.check_distribution import (
    _check_member_paths,
    _require_members,
    _required_package_members,
)


@pytest.mark.parametrize(
    "member",
    [
        "../outside.txt",
        "/absolute.txt",
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


def test_distribution_check_requires_phase_8_runtime_boundaries() -> None:
    required = _required_package_members("veridoc")

    assert "veridoc/administration/api.py" in required
    assert "veridoc/administration/cli.py" in required
    assert "veridoc/persistence/migrations.py" in required
    assert "veridoc/persistence/maintenance.py" in required
