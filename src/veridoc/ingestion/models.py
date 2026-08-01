"""Types shared by invoice ingestion steps."""

from dataclasses import dataclass
from typing import Literal

type SupportedMediaType = Literal[
    "application/pdf",
    "image/jpeg",
    "image/png",
]


@dataclass(frozen=True, slots=True)
class UploadedDocument:
    """A validated uploaded invoice with its original binary contents."""

    filename: str
    media_type: SupportedMediaType
    content: bytes
