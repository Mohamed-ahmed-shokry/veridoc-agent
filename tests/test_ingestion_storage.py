"""Temporary upload lifecycle tests."""

from pathlib import Path

from veridoc.ingestion.models import ValidatedUpload
from veridoc.ingestion.storage import temporary_upload


def test_temporary_upload_is_removed_after_context_exit() -> None:
    upload = ValidatedUpload(
        data=b"fictional invoice bytes",
        media_type="image/png",
        filename="invoice.png",
        suffix=".png",
        page_count=1,
        width=1,
        height=1,
    )

    temporary_path: Path | None = None
    temporary_directory: Path | None = None
    with temporary_upload(upload) as path:
        temporary_path = path
        temporary_directory = path.parent
        assert path.name == "document.png"
        assert path.read_bytes() == upload.data
        assert path.exists()

    assert temporary_path is not None
    assert temporary_directory is not None
    assert not temporary_path.exists()
    assert not temporary_directory.exists()
