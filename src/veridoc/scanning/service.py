"""Request-scoped orchestration for the scanning boundary.

``scan_upload_bytes`` is the single entry point the upload dependency calls
between signature validation and decoding: it resolves the configured
scanner, fails closed when scanning was requested but is unavailable, and
moves positives into operator-held quarantine before rejecting them. When
scanning is not enabled it returns immediately without touching the bytes.
"""

from __future__ import annotations

from veridoc.scanning.clamav import ClamAVScanner
from veridoc.scanning.config import ScanningSettings
from veridoc.scanning.protocol import ScanRejectedError, ScanUnavailableError
from veridoc.scanning.quarantine import QuarantineError, QuarantineStore


async def scan_upload_bytes(
    data: bytes,
    *,
    filename: str | None,
    declared_content_type: str | None,
) -> None:
    """Scan one bounded upload; raise a typed error unless it is clean."""
    settings = ScanningSettings.from_environment()
    if not settings.enabled:
        return
    scanner = ClamAVScanner(settings)
    store = QuarantineStore(settings.quarantine_directory)
    result = await scanner.scan(data)
    if result.clean:
        return
    try:
        store.quarantine(
            data,
            filename=filename,
            declared_content_type=declared_content_type,
            signature=result.signature or "unknown-detection",
            engine=result.engine,
            retention_days=settings.quarantine_retention_days,
        )
    except QuarantineError as exc:
        raise ScanUnavailableError from exc
    raise ScanRejectedError
