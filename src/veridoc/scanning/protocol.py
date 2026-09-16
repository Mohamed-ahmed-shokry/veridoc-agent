"""Typed scanner boundary, results, and safe domain errors."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol


class ScanRejectedError(RuntimeError):
    """Raised when a scanner flags an upload as malicious."""

    code = "document_scan_rejected"
    message = "The uploaded document was rejected by malware scanning."

    def __init__(self) -> None:
        super().__init__(self.message)


class ScanUnavailableError(RuntimeError):
    """Raised when scanning is enabled but the scanner cannot be used."""

    code = "document_scan_unavailable"
    message = "Document scanning is not available on this server."

    def __init__(self) -> None:
        super().__init__(self.message)


@dataclass(frozen=True, slots=True)
class ScanResult:
    """The typed outcome of one upload scan."""

    clean: bool
    engine: str
    signature: str | None = None


class MalwareScanner(Protocol):
    """A replaceable upload scanner that fails closed on errors."""

    async def scan(self, data: bytes) -> ScanResult:
        """Scan one bounded upload; raise on any scanner failure."""
        ...
