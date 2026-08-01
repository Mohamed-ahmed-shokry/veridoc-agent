"""Internal models produced by the Phase 1 upload validator."""

from dataclasses import dataclass
from typing import Literal

DocumentMediaType = Literal["application/pdf", "image/jpeg", "image/png"]


@dataclass(frozen=True, slots=True)
class ValidatedUpload:
    """A bounded document whose media signature and dimensions were checked."""

    data: bytes
    media_type: DocumentMediaType
    filename: str
    suffix: str
    page_count: int
    width: int | None = None
    height: int | None = None
