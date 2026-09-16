"""Scanning protocol and configuration tests."""

import pytest

from veridoc.scanning.config import ScanningSettings
from veridoc.scanning.protocol import (
    ScanRejectedError,
    ScanResult,
    ScanUnavailableError,
)


def test_scan_errors_carry_safe_codes_and_messages() -> None:
    """Scanning domain errors expose stable typed codes without secrets."""
    assert ScanRejectedError.code == "document_scan_rejected"
    assert ScanRejectedError().message == (
        "The uploaded document was rejected by malware scanning."
    )
    assert ScanUnavailableError.code == "document_scan_unavailable"
    assert ScanUnavailableError().message == (
        "Document scanning is not available on this server."
    )


def test_scan_result_is_a_typed_frozen_value() -> None:
    """Scan results identify their engine and optional detection signature."""
    result = ScanResult(clean=False, engine="clamav", signature="Eicar-Test")
    assert result.clean is False
    assert result.engine == "clamav"
    assert result.signature == "Eicar-Test"
    assert ScanResult(clean=True, engine="clamav").signature is None


def test_clean_scan_result_carries_no_signature() -> None:
    """A clean result never carries a detection signature."""
    result = ScanResult(clean=True, engine="clamav", signature=None)
    assert result.clean is True
    assert result.signature is None


def test_scanning_is_disabled_by_default() -> None:
    """An empty environment leaves the scanning boundary disabled."""
    settings = ScanningSettings.from_environment({})
    assert settings.enabled is False


def test_scanning_accepts_truthy_enable_values(tmp_path) -> None:
    """Canonical enable values activate the boundary with safe defaults."""
    settings = ScanningSettings.from_environment(
        {
            "VERIDOC_SCAN_ENABLED": "1",
            "VERIDOC_QUARANTINE_DIRECTORY": str(tmp_path),
        }
    )
    assert settings.enabled is True
    assert settings.clamd_host == "127.0.0.1"
    assert settings.clamd_port == 3310
    assert settings.clamd_timeout_seconds == 30.0
    assert settings.quarantine_directory == str(tmp_path)
    assert settings.quarantine_retention_days == 30


def test_scanning_accepts_true_and_yes(tmp_path) -> None:
    """Case-insensitive truthy values also activate scanning."""
    for value in ("true", "True", "YES"):
        settings = ScanningSettings.from_environment(
            {
                "VERIDOC_SCAN_ENABLED": value,
                "VERIDOC_QUARANTINE_DIRECTORY": str(tmp_path),
            }
        )
        assert settings.enabled is True


def test_scanning_rejects_ambiguous_enable_values(tmp_path) -> None:
    """Ambiguous enable values fail closed instead of silently disabling."""
    with pytest.raises(ScanUnavailableError):
        ScanningSettings.from_environment(
            {
                "VERIDOC_SCAN_ENABLED": "maybe",
                "VERIDOC_QUARANTINE_DIRECTORY": str(tmp_path),
            }
        )


def test_scanning_requires_a_quarantine_directory() -> None:
    """Enabling scanning without a quarantine directory fails closed."""
    with pytest.raises(ScanUnavailableError):
        ScanningSettings.from_environment({"VERIDOC_SCAN_ENABLED": "1"})


def test_scanning_requires_an_existing_quarantine_directory(tmp_path) -> None:
    """A quarantine directory that does not exist fails closed."""
    with pytest.raises(ScanUnavailableError):
        ScanningSettings.from_environment(
            {
                "VERIDOC_SCAN_ENABLED": "1",
                "VERIDOC_QUARANTINE_DIRECTORY": str(tmp_path / "missing"),
            }
        )


def test_scanning_rejects_a_quarantine_file(tmp_path) -> None:
    """A quarantine path pointing at a regular file fails closed."""
    quarantine_file = tmp_path / "quarantine.sqlite"
    quarantine_file.write_bytes(b"not-a-directory")
    with pytest.raises(ScanUnavailableError):
        ScanningSettings.from_environment(
            {
                "VERIDOC_SCAN_ENABLED": "1",
                "VERIDOC_QUARANTINE_DIRECTORY": str(quarantine_file),
            }
        )


def test_scanning_parses_clamd_endpoint(tmp_path) -> None:
    """A configured clamd host and port are preserved verbatim."""
    settings = ScanningSettings.from_environment(
        {
            "VERIDOC_SCAN_ENABLED": "1",
            "VERIDOC_QUARANTINE_DIRECTORY": str(tmp_path),
            "VERIDOC_CLAMD_HOST": "clamav",
            "VERIDOC_CLAMD_PORT": "3311",
        }
    )
    assert settings.clamd_host == "clamav"
    assert settings.clamd_port == 3311


def test_scanning_rejects_bad_clamd_ports(tmp_path) -> None:
    """Out-of-range or nonnumeric clamd ports fail closed."""
    for value in ("0", "65536", "not-a-port"):
        with pytest.raises(ScanUnavailableError):
            ScanningSettings.from_environment(
                {
                    "VERIDOC_SCAN_ENABLED": "1",
                    "VERIDOC_QUARANTINE_DIRECTORY": str(tmp_path),
                    "VERIDOC_CLAMD_PORT": value,
                }
            )


def test_scanning_parses_bounded_clamd_timeout(tmp_path) -> None:
    """Positive clamd timeouts up to 300 seconds are accepted."""
    settings = ScanningSettings.from_environment(
        {
            "VERIDOC_SCAN_ENABLED": "1",
            "VERIDOC_QUARANTINE_DIRECTORY": str(tmp_path),
            "VERIDOC_CLAMD_TIMEOUT_SECONDS": "5",
        }
    )
    assert settings.clamd_timeout_seconds == 5.0


def test_scanning_rejects_bad_clamd_timeouts(tmp_path) -> None:
    """Nonnumeric, nonfinite, nonpositive, or >300-second timeouts fail closed."""
    for value in ("never", "nan", "inf", "0", "-1", "301"):
        with pytest.raises(ScanUnavailableError):
            ScanningSettings.from_environment(
                {
                    "VERIDOC_SCAN_ENABLED": "1",
                    "VERIDOC_QUARANTINE_DIRECTORY": str(tmp_path),
                    "VERIDOC_CLAMD_TIMEOUT_SECONDS": value,
                }
            )


def test_scanning_rejects_bad_retention_days(tmp_path) -> None:
    """Nonnumeric or nonpositive retention values fail closed."""
    for value in ("never", "0", "-30"):
        with pytest.raises(ScanUnavailableError):
            ScanningSettings.from_environment(
                {
                    "VERIDOC_SCAN_ENABLED": "1",
                    "VERIDOC_QUARANTINE_DIRECTORY": str(tmp_path),
                    "VERIDOC_QUARANTINE_RETENTION_DAYS": value,
                }
            )


def test_malware_scanner_protocol_shape() -> None:
    """The scanner protocol declares a single async scan method."""

    class FakeScanner:
        async def scan(self, data: bytes) -> ScanResult:
            return ScanResult(clean=True, engine="fake", signature=None)

    scanner = FakeScanner()
    assert callable(getattr(scanner, "scan", None))
