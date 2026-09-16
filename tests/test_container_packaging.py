"""Tests for Phase 10 reproducible container packaging contracts."""

from __future__ import annotations

from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
_DOCKERFILE = _ROOT / "Dockerfile"
_DOCKERIGNORE = _ROOT / ".dockerignore"
_ENTRYPOINT = _ROOT / "scripts" / "entrypoint.sh"


def test_dockerfile_exists_and_declares_pinned_base_image() -> None:
    """Dockerfile must use a pinned Python 3.12 base image."""
    assert _DOCKERFILE.is_file(), "Dockerfile must exist at the repository root."
    content = _DOCKERFILE.read_text(encoding="utf-8")

    assert "FROM python:3.12" in content
    assert "slim" in content


def test_dockerfile_installs_required_tesseract_languages() -> None:
    """Dockerfile must install Tesseract OCR with English and Arabic packages."""
    content = _DOCKERFILE.read_text(encoding="utf-8")

    assert "tesseract-ocr" in content
    assert "tesseract-ocr-eng" in content
    assert "tesseract-ocr-ara" in content


def test_dockerfile_enforces_non_root_runtime_user() -> None:
    """Container must run as a non-root user with declared UID."""
    content = _DOCKERFILE.read_text(encoding="utf-8")

    assert "useradd" in content
    assert "10001" in content
    assert "USER veridoc:veridoc" in content


def test_dockerfile_declares_runtime_mounts_and_environment() -> None:
    """Dockerfile must declare storage mounts and production environment defaults."""
    content = _DOCKERFILE.read_text(encoding="utf-8")

    assert "/data" in content
    assert "/secrets" in content
    assert "VERIDOC_REFERENCE_DATABASE" in content
    assert "VERIDOC_REVIEW_DATABASE" in content
    assert "ENTRYPOINT" in content
    assert "uvicorn" in content


def test_dockerignore_excludes_sensitive_and_ephemeral_paths() -> None:
    """.dockerignore must exclude git, virtualenvs, local databases, and caches."""
    assert _DOCKERIGNORE.is_file(), ".dockerignore must exist at repository root."
    ignored = {
        line.strip()
        for line in _DOCKERIGNORE.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.startswith("#")
    }

    assert ".git" in ignored
    assert ".venv" in ignored
    assert ".env" in ignored
    assert "*.sqlite3" in ignored
    assert "tests" in ignored


def test_entrypoint_script_injects_secrets_without_leaking() -> None:
    """Entrypoint script must export secrets conditionally without printing them."""
    assert _ENTRYPOINT.is_file(), "scripts/entrypoint.sh must exist."
    content = _ENTRYPOINT.read_text(encoding="utf-8")

    assert "set -eu" in content
    assert "OPENAI_API_KEY" in content
    assert "VERIDOC_ADMIN_TOKEN" in content
    assert "VERIDOC_REVIEW_ACTORS_FILE" in content
    assert 'exec "$@"' in content
    # Secrets must not be echoed or printed
    assert "echo" not in content
    assert "printf" not in content
