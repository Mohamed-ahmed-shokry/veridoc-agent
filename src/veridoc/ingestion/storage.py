"""Ephemeral storage helpers for validated document processing."""

from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from tempfile import TemporaryDirectory

from veridoc.ingestion.models import ValidatedUpload


@contextmanager
def temporary_upload(upload: ValidatedUpload) -> Iterator[Path]:
    """Yield a private temporary path and remove it on every exit path."""
    with TemporaryDirectory(prefix="veridoc-upload-") as directory:
        path = Path(directory) / f"document{upload.suffix}"
        path.write_bytes(upload.data)
        yield path
