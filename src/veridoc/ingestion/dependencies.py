"""Shared FastAPI dependency for validating one uploaded document.

Kept separate from ``veridoc.ingestion.validation`` (which stays free of
FastAPI request/response types) so both ``veridoc.app`` and
``veridoc.review.api`` can depend on the same validated-upload boundary
without importing from each other.
"""

from __future__ import annotations

from asyncio import to_thread
from typing import Annotated

from fastapi import File, HTTPException, UploadFile

from veridoc.ingestion.models import ValidatedUpload
from veridoc.ingestion.validation import (
    UploadValidationError,
    decode_validated_upload,
    read_bounded_upload,
    validate_upload_head,
)
from veridoc.scanning.protocol import ScanRejectedError, ScanUnavailableError
from veridoc.scanning.service import scan_upload_bytes


async def get_validated_upload(
    file: Annotated[UploadFile, File(description="A PDF, PNG, or JPEG invoice.")],
) -> ValidatedUpload:
    """Read, scan, validate, and close one upload before dependencies resolve."""
    try:
        data = await read_bounded_upload(file)
        pending = await to_thread(
            validate_upload_head,
            data,
            filename=file.filename,
            declared_content_type=file.content_type,
        )
        await scan_upload_bytes(
            pending.data,
            filename=pending.filename,
            declared_content_type=file.content_type,
        )
        return await to_thread(decode_validated_upload, pending)
    except UploadValidationError as exc:
        raise HTTPException(
            status_code=exc.status_code,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ScanRejectedError as exc:
        raise HTTPException(
            status_code=422,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    except ScanUnavailableError as exc:
        raise HTTPException(
            status_code=503,
            detail={"code": exc.code, "message": exc.message},
        ) from exc
    finally:
        await file.close()
