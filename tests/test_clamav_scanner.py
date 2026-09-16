"""ClamAV adapter tests against a fake in-process clamd daemon."""

import socket
import struct
import threading

import pytest

from veridoc.scanning.clamav import ClamAVScanner
from veridoc.scanning.config import ScanningSettings
from veridoc.scanning.protocol import ScanUnavailableError


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous scanner tests on the standard event loop."""
    return "asyncio"


class FakeClamd:
    """A minimal in-process clamd daemon speaking zINSTREAM over TCP."""

    def __init__(self, response: bytes, *, accept_count: int = 1) -> None:
        self._response = response
        self._accept_count = accept_count
        self.received = bytearray()
        self._server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self._server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self._server.bind(("127.0.0.1", 0))
        self._server.listen(8)
        self.port = self._server.getsockname()[1]
        self._thread = threading.Thread(target=self._serve, daemon=True)
        self._thread.start()

    def _serve(self) -> None:
        for _ in range(self._accept_count):
            try:
                connection, _ = self._server.accept()
            except OSError:
                return
            with connection:
                connection.settimeout(5.0)
                try:
                    self._read_stream(connection)
                    connection.sendall(self._response)
                except OSError:
                    return
        self._server.close()

    def _read_stream(self, connection: socket.socket) -> None:
        command = b""
        while not command.endswith(b"\0"):
            chunk = connection.recv(64)
            if not chunk:
                return
            command += chunk
        while True:
            header = self._recv_exact(connection, 4)
            (length,) = struct.unpack(">I", header)
            if length == 0:
                return
            self.received.extend(self._recv_exact(connection, length))

    @staticmethod
    def _recv_exact(connection: socket.socket, count: int) -> bytes:
        data = bytearray()
        while len(data) < count:
            chunk = connection.recv(count - len(data))
            if not chunk:
                raise OSError("connection closed mid-stream")
            data.extend(chunk)
        return bytes(data)

    def settings(self, tmp_path, **overrides) -> ScanningSettings:
        values: dict[str, str] = {
            "VERIDOC_SCAN_ENABLED": "1",
            "VERIDOC_QUARANTINE_DIRECTORY": str(tmp_path),
            "VERIDOC_CLAMD_HOST": "127.0.0.1",
            "VERIDOC_CLAMD_PORT": str(self.port),
            "VERIDOC_CLAMD_TIMEOUT_SECONDS": "5",
        }
        values.update(overrides)
        return ScanningSettings.from_environment(values)


@pytest.mark.anyio
async def test_clamav_clean_upload_returns_clean_result(tmp_path) -> None:
    """A clamd OK verdict maps to a clean typed result."""
    daemon = FakeClamd(b"stream: OK\n")
    scanner = ClamAVScanner(daemon.settings(tmp_path))

    result = await scanner.scan(b"%PDF-1.4 fictional-bytes")

    assert result.clean is True
    assert result.engine == "clamav"
    assert result.signature is None
    assert bytes(daemon.received) == b"%PDF-1.4 fictional-bytes"


@pytest.mark.anyio
async def test_clamav_found_verdict_returns_signature(tmp_path) -> None:
    """A clamd FOUND verdict returns its detection signature."""
    daemon = FakeClamd(b"stream: Eicar-Test-Signature FOUND\n")
    scanner = ClamAVScanner(daemon.settings(tmp_path))

    result = await scanner.scan(b"X5O!P%@AP[4\\PZX54(P^)7CC)7}$EICAR")

    assert result.clean is False
    assert result.engine == "clamav"
    assert result.signature == "Eicar-Test-Signature"


@pytest.mark.anyio
async def test_clamav_malformed_response_fails_closed(tmp_path) -> None:
    """A protocol-violating daemon response maps to the unavailable error."""
    daemon = FakeClamd(b"definitely-not-a-clamd-response\n")
    scanner = ClamAVScanner(daemon.settings(tmp_path))

    with pytest.raises(ScanUnavailableError):
        await scanner.scan(b"some-bytes")


@pytest.mark.anyio
async def test_clamav_empty_signature_fails_closed(tmp_path) -> None:
    """A FOUND verdict without a signature maps to the unavailable error."""
    daemon = FakeClamd(b"stream:  FOUND\n")
    scanner = ClamAVScanner(daemon.settings(tmp_path))

    with pytest.raises(ScanUnavailableError):
        await scanner.scan(b"some-bytes")


def test_clamav_refuses_disabled_settings(tmp_path) -> None:
    """Constructing the adapter while disabled raises the unavailable error."""
    settings = ScanningSettings.from_environment({})
    with pytest.raises(ScanUnavailableError):
        ClamAVScanner(settings)


@pytest.mark.anyio
async def test_clamav_connection_refused_fails_closed(tmp_path) -> None:
    """An unreachable daemon maps to the unavailable error."""
    reserved = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    reserved.bind(("127.0.0.1", 0))
    unused_port = str(reserved.getsockname()[1])
    reserved.close()

    values = {
        "VERIDOC_SCAN_ENABLED": "1",
        "VERIDOC_QUARANTINE_DIRECTORY": str(tmp_path),
        "VERIDOC_CLAMD_HOST": "127.0.0.1",
        "VERIDOC_CLAMD_PORT": unused_port,
        "VERIDOC_CLAMD_TIMEOUT_SECONDS": "2",
    }
    scanner = ClamAVScanner(ScanningSettings.from_environment(values))

    with pytest.raises(ScanUnavailableError):
        await scanner.scan(b"some-bytes")


@pytest.mark.anyio
async def test_clamav_slow_daemon_hits_the_application_deadline(tmp_path) -> None:
    """A daemon that never answers is bounded by the configured deadline."""
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", 0))
    server.listen(1)
    port = server.getsockname()[1]

    def accept_and_hang() -> None:
        connection, _ = server.accept()
        with connection:
            connection.settimeout(5.0)
            try:
                while connection.recv(4096):
                    pass
            except OSError:
                pass

    thread = threading.Thread(target=accept_and_hang, daemon=True)
    thread.start()
    try:
        values = {
            "VERIDOC_SCAN_ENABLED": "1",
            "VERIDOC_QUARANTINE_DIRECTORY": str(tmp_path),
            "VERIDOC_CLAMD_HOST": "127.0.0.1",
            "VERIDOC_CLAMD_PORT": str(port),
            "VERIDOC_CLAMD_TIMEOUT_SECONDS": "1",
        }
        scanner = ClamAVScanner(ScanningSettings.from_environment(values))
        with pytest.raises(ScanUnavailableError):
            await scanner.scan(b"some-bytes")
    finally:
        server.close()
