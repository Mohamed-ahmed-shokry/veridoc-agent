"""ClamAV adapter for the scanning boundary.

The adapter streams one bounded upload to a local ``clamd`` daemon over its
documented ``zINSTREAM`` TCP command. Every socket or protocol failure maps
to the safe unavailable error so the upload dependency fails closed.
Blocking socket I/O runs in a worker thread under a bounded application
deadline; the socket itself carries the same timeout as a second bound.
"""

from __future__ import annotations

import asyncio
import socket
import struct
from asyncio import to_thread

from veridoc.scanning.config import ScanningSettings
from veridoc.scanning.protocol import ScanResult, ScanUnavailableError

_ENGINE = "clamav"
_CHUNK_SIZE = 64 * 1024


class ClamAVScanner:
    """Scan one bounded upload through a local clamd daemon."""

    def __init__(self, settings: ScanningSettings) -> None:
        if not settings.enabled:
            raise ScanUnavailableError
        self._settings = settings

    async def scan(self, data: bytes) -> ScanResult:
        """Stream the upload to clamd and return its typed verdict."""
        try:
            return await asyncio.wait_for(
                to_thread(self._scan_sync, data),
                timeout=self._settings.clamd_timeout_seconds,
            )
        except TimeoutError as exc:
            raise ScanUnavailableError from exc

    def _scan_sync(self, data: bytes) -> ScanResult:
        settings = self._settings
        try:
            with socket.create_connection(
                (settings.clamd_host, settings.clamd_port),
                timeout=settings.clamd_timeout_seconds,
            ) as connection:
                connection.settimeout(settings.clamd_timeout_seconds)
                connection.sendall(b"zINSTREAM\0")
                for offset in range(0, len(data), _CHUNK_SIZE):
                    chunk = data[offset : offset + _CHUNK_SIZE]
                    connection.sendall(struct.pack(">I", len(chunk)) + chunk)
                connection.sendall(struct.pack(">I", 0))
                response = _read_response(connection)
        except (OSError, UnicodeDecodeError) as exc:
            raise ScanUnavailableError from exc
        return _parse_response(response)


def _read_response(connection: socket.socket) -> str:
    chunks: list[bytes] = []
    while True:
        try:
            chunk = connection.recv(4096)
        except TimeoutError as exc:
            raise ScanUnavailableError from exc
        if not chunk:
            break
        chunks.append(chunk)
        if len(chunks) > 16:
            break
    return b"".join(chunks).decode("utf-8", errors="strict")


def _parse_response(response: str) -> ScanResult:
    cleaned = response.strip()
    if cleaned.endswith("OK"):
        return ScanResult(clean=True, engine=_ENGINE)
    if cleaned.startswith("stream: ") and cleaned.endswith(" FOUND"):
        signature = cleaned[len("stream: ") : -len(" FOUND")].strip()
        if signature:
            return ScanResult(clean=False, engine=_ENGINE, signature=signature)
    raise ScanUnavailableError
