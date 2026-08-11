"""Authenticated FastAPI routes for reference-data administration."""

from __future__ import annotations

import os
from typing import Annotated

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Path,
    Query,
    Security,
    UploadFile,
    status,
)
from fastapi.responses import Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import ValidationError
from starlette.concurrency import run_in_threadpool

from veridoc.administration.auth import (
    AdminAuthenticationUnavailableError,
    AdminSettings,
    InvalidAdminCredentialsError,
    authorize_admin,
)
from veridoc.administration.models import (
    MAX_ADMIN_IMPORT_BYTES,
    ConflictPolicy,
    ImportResult,
    InvoiceRecord,
    InvoiceRecordInput,
    InvoiceRecordPage,
    InvoiceRecordUpdate,
    PurchaseOrderRecord,
    PurchaseOrderRecordInput,
    PurchaseOrderRecordPage,
    PurchaseOrderRecordUpdate,
    ReferenceDataImport,
    VendorKey,
)
from veridoc.administration.protocol import (
    ReferenceDataAdminRepository,
    ReferenceDataConflictError,
)
from veridoc.persistence.sqlite import SQLiteInvoiceRepository

router = APIRouter(
    prefix="/admin/reference-data",
    tags=["reference-data-administration"],
)

_ADMIN_BEARER = HTTPBearer(
    auto_error=False,
    scheme_name="AdminBearer",
    description="Local reference-data administration token.",
)
_RECORD_ID = Path(
    min_length=1,
    max_length=128,
    pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$",
)


def require_admin(
    credentials: Annotated[
        HTTPAuthorizationCredentials | None,
        Security(_ADMIN_BEARER),
    ],
) -> None:
    """Require valid configured administration credentials."""
    try:
        settings = AdminSettings.from_environment()
    except AdminAuthenticationUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail={"code": exc.code, "message": exc.message},
        ) from exc

    authorization = (
        f"{credentials.scheme} {credentials.credentials}"
        if credentials is not None
        else None
    )
    try:
        authorize_admin(authorization, settings)
    except InvalidAdminCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": exc.code, "message": exc.message},
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc


def get_admin_repository() -> ReferenceDataAdminRepository:
    """Open the configured local reference-data administration adapter."""
    database_path = os.environ.get(
        "VERIDOC_REFERENCE_DATABASE", "veridoc-reference.sqlite3"
    ).strip()
    repository = SQLiteInvoiceRepository(database_path or "veridoc-reference.sqlite3")
    repository.initialize()
    return repository


def get_authorized_admin_repository(
    _: Annotated[None, Depends(require_admin)],
    repository: Annotated[
        ReferenceDataAdminRepository,
        Depends(get_admin_repository),
    ],
) -> ReferenceDataAdminRepository:
    """Resolve storage only after the request passes authentication."""
    return repository


@router.post(
    "/invoices",
    response_model=InvoiceRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_invoice(
    record: InvoiceRecordInput,
    repository: Annotated[
        ReferenceDataAdminRepository,
        Depends(get_authorized_admin_repository),
    ],
) -> InvoiceRecord:
    """Create one provenance-tracked historical invoice."""
    try:
        return repository.create_invoice(record)
    except ReferenceDataConflictError as exc:
        raise _conflict(exc) from exc


@router.get("/invoices", response_model=InvoiceRecordPage)
def list_invoices(
    repository: Annotated[
        ReferenceDataAdminRepository,
        Depends(get_authorized_admin_repository),
    ],
    vendor_key: Annotated[VendorKey | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> InvoiceRecordPage:
    """Return a bounded page of managed invoices."""
    return repository.list_invoices(
        vendor_key=vendor_key,
        offset=offset,
        limit=limit,
    )


@router.get("/invoices/{record_id}", response_model=InvoiceRecord)
def get_invoice(
    record_id: Annotated[str, _RECORD_ID],
    repository: Annotated[
        ReferenceDataAdminRepository,
        Depends(get_authorized_admin_repository),
    ],
) -> InvoiceRecord:
    """Return one managed invoice without document content."""
    record = repository.get_admin_invoice(record_id)
    if record is None:
        raise _not_found()
    return record


@router.put("/invoices/{record_id}", response_model=InvoiceRecord)
def update_invoice(
    record_id: Annotated[str, _RECORD_ID],
    update: InvoiceRecordUpdate,
    repository: Annotated[
        ReferenceDataAdminRepository,
        Depends(get_authorized_admin_repository),
    ],
) -> InvoiceRecord:
    """Replace mutable invoice facts while preserving provenance."""
    record = repository.update_admin_invoice(record_id, update)
    if record is None:
        raise _not_found()
    return record


@router.delete(
    "/invoices/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_invoice(
    record_id: Annotated[str, _RECORD_ID],
    repository: Annotated[
        ReferenceDataAdminRepository,
        Depends(get_authorized_admin_repository),
    ],
) -> Response:
    """Delete one managed invoice and its line items."""
    if not repository.delete_admin_invoice(record_id):
        raise _not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post(
    "/purchase-orders",
    response_model=PurchaseOrderRecord,
    status_code=status.HTTP_201_CREATED,
)
def create_purchase_order(
    record: PurchaseOrderRecordInput,
    repository: Annotated[
        ReferenceDataAdminRepository,
        Depends(get_authorized_admin_repository),
    ],
) -> PurchaseOrderRecord:
    """Create one provenance-tracked purchase order."""
    try:
        return repository.create_purchase_order(record)
    except ReferenceDataConflictError as exc:
        raise _conflict(exc) from exc


@router.get("/purchase-orders", response_model=PurchaseOrderRecordPage)
def list_purchase_orders(
    repository: Annotated[
        ReferenceDataAdminRepository,
        Depends(get_authorized_admin_repository),
    ],
    vendor_key: Annotated[VendorKey | None, Query()] = None,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=200)] = 100,
) -> PurchaseOrderRecordPage:
    """Return a bounded page of managed purchase orders."""
    return repository.list_purchase_orders(
        vendor_key=vendor_key,
        offset=offset,
        limit=limit,
    )


@router.get("/purchase-orders/{record_id}", response_model=PurchaseOrderRecord)
def get_purchase_order(
    record_id: Annotated[str, _RECORD_ID],
    repository: Annotated[
        ReferenceDataAdminRepository,
        Depends(get_authorized_admin_repository),
    ],
) -> PurchaseOrderRecord:
    """Return one managed purchase order without document content."""
    record = repository.get_admin_purchase_order(record_id)
    if record is None:
        raise _not_found()
    return record


@router.put("/purchase-orders/{record_id}", response_model=PurchaseOrderRecord)
def update_purchase_order(
    record_id: Annotated[str, _RECORD_ID],
    update: PurchaseOrderRecordUpdate,
    repository: Annotated[
        ReferenceDataAdminRepository,
        Depends(get_authorized_admin_repository),
    ],
) -> PurchaseOrderRecord:
    """Replace mutable purchase-order facts while preserving provenance."""
    try:
        record = repository.update_admin_purchase_order(record_id, update)
    except ReferenceDataConflictError as exc:
        raise _conflict(exc) from exc
    if record is None:
        raise _not_found()
    return record


@router.delete(
    "/purchase-orders/{record_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def delete_purchase_order(
    record_id: Annotated[str, _RECORD_ID],
    repository: Annotated[
        ReferenceDataAdminRepository,
        Depends(get_authorized_admin_repository),
    ],
) -> Response:
    """Delete one managed purchase order and its line items."""
    if not repository.delete_admin_purchase_order(record_id):
        raise _not_found()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/import", response_model=ImportResult)
async def import_reference_data(
    file: Annotated[
        UploadFile,
        File(description="A bounded UTF-8 JSON reference-data batch."),
    ],
    repository: Annotated[
        ReferenceDataAdminRepository,
        Depends(get_authorized_admin_repository),
    ],
    conflict: Annotated[ConflictPolicy, Query()] = "reject",
    dry_run: Annotated[bool, Query()] = False,
) -> ImportResult:
    """Validate and atomically apply or simulate one reference-data import."""
    try:
        if (file.content_type or "").split(";", 1)[0].strip() != "application/json":
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail={
                    "code": "unsupported_import_media_type",
                    "message": "Reference-data imports must use application/json.",
                },
            )
        payload = await file.read(MAX_ADMIN_IMPORT_BYTES + 1)
        if len(payload) > MAX_ADMIN_IMPORT_BYTES:
            raise HTTPException(
                status_code=status.HTTP_413_CONTENT_TOO_LARGE,
                detail={
                    "code": "reference_data_import_too_large",
                    "message": "The reference-data import exceeds the size limit.",
                },
            )
        try:
            batch = ReferenceDataImport.model_validate_json(payload)
        except ValidationError as exc:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail={
                    "code": "invalid_reference_data_import",
                    "message": "The reference-data import is invalid.",
                },
            ) from exc
        try:
            return await run_in_threadpool(
                repository.import_reference_data,
                batch,
                conflict=conflict,
                dry_run=dry_run,
            )
        except ReferenceDataConflictError as exc:
            raise _conflict(exc) from exc
    finally:
        await file.close()


def _not_found() -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail={
            "code": "reference_record_not_found",
            "message": "The reference-data record was not found.",
        },
    )


def _conflict(exc: ReferenceDataConflictError) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={"code": exc.code, "message": exc.message},
    )
