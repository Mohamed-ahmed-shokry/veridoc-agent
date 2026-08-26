"""Retry, concurrency, backup/restore, and snapshot-independence integration.

Complements test_review_case_creation_integration.py (real processing graph)
and test_review_persistence_concurrency.py (repository-level races): this
module proves three end-to-end properties that only show up when the full
HTTP stack, the real processing graph, and the maintenance CLI functions are
exercised together.
"""

from __future__ import annotations

import asyncio
from hashlib import sha256
from io import BytesIO
from pathlib import Path

import httpx
import pytest
from PIL import Image

from veridoc.app import app, get_ocr_engine, get_structured_extractor
from veridoc.explanation.service import ExplanationService
from veridoc.extraction.models import InvoiceExtraction
from veridoc.extraction.protocol import ExtractionRequest
from veridoc.ocr.models import OCRPageResult
from veridoc.persistence.sqlite import SQLiteInvoiceRepository
from veridoc.processing.dependencies import (
    get_explanation_service,
    get_processing_service,
)
from veridoc.processing.models import ProcessingResult, ProcessingVerdict
from veridoc.review.api import (
    CSRF_HEADER_NAME,
    IDEMPOTENCY_KEY_HEADER,
    get_review_actor_directory,
    get_review_origin_settings,
    get_review_repository,
)
from veridoc.review.config import (
    ReviewActor,
    ReviewActorDirectory,
    ReviewOriginSettings,
)
from veridoc.review.models import CaseAssignmentRequest
from veridoc.review.persistence.maintenance import backup_database, restore_database
from veridoc.review.persistence.sqlite import SQLiteReviewRepository
from veridoc.verification.references import HistoricalInvoice

_REVIEWER_SECRET = "reviewer-secret-value"
_ORIGIN = "https://review.example"


def _digest(secret: str) -> str:
    return sha256(secret.encode("utf-8")).hexdigest()


def _directory() -> ReviewActorDirectory:
    return ReviewActorDirectory(
        _actors_by_id={
            "reviewer-1": ReviewActor(
                actor_id="reviewer-1",
                role="reviewer",
                secret_digest=_digest(_REVIEWER_SECRET),
            )
        }
    )


def _png_bytes() -> bytes:
    output = BytesIO()
    Image.new("RGB", (16, 8), color="white").save(output, format="PNG")
    return output.getvalue()


def _result(*, invoice_number: str) -> ProcessingResult:
    return ProcessingResult(
        extraction=InvoiceExtraction(
            document_type="invoice", invoice_number=invoice_number
        ),
        verdict=ProcessingVerdict(
            status="clear",
            summary="No deterministic verification findings require review.",
            finding_count=0,
        ),
    )


class _FakeProcessingService:
    def __init__(self, *, invoice_number: str = "INV-001") -> None:
        self._invoice_number = invoice_number

    async def process(self, upload):
        del upload
        return _result(invoice_number=self._invoice_number)


class _IntegrationOCREngine:
    def recognize(self, image: Image.Image) -> OCRPageResult:
        assert image.mode == "RGB"
        return OCRPageResult(text="Invoice No: INV-002", confidence=88.0)


class _IntegrationExtractor:
    async def extract(self, request: ExtractionRequest) -> InvoiceExtraction:
        return InvoiceExtraction(
            document_type="invoice",
            vendor_name="Fictional Supplies Ltd.",
            invoice_number="INV-002",
            ocr_confidence=request.document.confidence,
        )


@pytest.fixture
def anyio_backend() -> str:
    """Run asynchronous endpoint tests on the standard event loop."""
    return "asyncio"


async def _login(client: httpx.AsyncClient) -> dict[str, str]:
    login = await client.post(
        "/review/session",
        headers={"Authorization": f"Bearer {_REVIEWER_SECRET}", "Origin": _ORIGIN},
    )
    client.cookies.set(
        "veridoc_review_session", login.cookies["veridoc_review_session"]
    )
    client.cookies.set("veridoc_review_csrf", login.cookies["veridoc_review_csrf"])
    return {
        "Origin": _ORIGIN,
        CSRF_HEADER_NAME: login.cookies["veridoc_review_csrf"],
    }


@pytest.mark.anyio
async def test_case_snapshot_is_independent_of_later_reference_data_changes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    reference_v1 = tmp_path / "reference-v1.sqlite"
    repository_v1 = SQLiteInvoiceRepository(reference_v1)
    repository_v1.initialize()
    repository_v1.add_invoice(
        HistoricalInvoice(vendor_key="fictional-supplies-ltd", invoice_number="INV-002")
    )
    reference_v2 = tmp_path / "reference-v2.sqlite"
    SQLiteInvoiceRepository(reference_v2).initialize()

    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("VERIDOC_LLM_MODEL", raising=False)
    review_repository = SQLiteReviewRepository(tmp_path / "review.sqlite")
    review_repository.initialize()
    app.dependency_overrides[get_ocr_engine] = _IntegrationOCREngine
    app.dependency_overrides[get_structured_extractor] = _IntegrationExtractor
    app.dependency_overrides[get_explanation_service] = lambda: ExplanationService()
    app.dependency_overrides[get_review_repository] = lambda: review_repository
    app.dependency_overrides[get_review_actor_directory] = _directory
    app.dependency_overrides[get_review_origin_settings] = lambda: ReviewOriginSettings(
        origin=_ORIGIN
    )

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            headers = await _login(client)

            monkeypatch.setenv("VERIDOC_REFERENCE_DATABASE", str(reference_v1))
            first = await client.post(
                "/review/cases",
                headers={**headers, IDEMPOTENCY_KEY_HEADER: "duplicate-check-1"},
                files={"file": ("invoice.png", _png_bytes(), "image/png")},
            )
            assert first.status_code == 201
            assert (
                first.json()["snapshot"]["result"]["verdict"]["status"]
                == "review_required"
            )
            first_case_id = first.json()["case_id"]

            monkeypatch.setenv("VERIDOC_REFERENCE_DATABASE", str(reference_v2))
            second = await client.post(
                "/review/cases",
                headers={**headers, IDEMPOTENCY_KEY_HEADER: "duplicate-check-2"},
                files={"file": ("invoice.png", _png_bytes(), "image/png")},
            )
            assert second.status_code == 201
            assert second.json()["snapshot"]["result"]["verdict"]["status"] == "clear"

            refetched = await client.get(
                f"/review/cases/{first_case_id}", headers=headers
            )
    finally:
        app.dependency_overrides.clear()

    assert refetched.status_code == 200
    refetched_result = refetched.json()["snapshot"]["result"]
    assert refetched_result["verdict"]["status"] == "review_required"
    assert refetched_result["findings"][0]["finding_type"] == "duplicate_invoice_number"


@pytest.mark.anyio
async def test_concurrent_claims_over_http_have_exactly_one_winner(
    tmp_path: Path,
) -> None:
    repository = SQLiteReviewRepository(tmp_path / "review.sqlite")
    repository.initialize()
    app.dependency_overrides[get_review_repository] = lambda: repository
    app.dependency_overrides[get_review_actor_directory] = _directory
    app.dependency_overrides[get_review_origin_settings] = lambda: ReviewOriginSettings(
        origin=_ORIGIN
    )
    app.dependency_overrides[get_processing_service] = _FakeProcessingService

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            headers = await _login(client)
            created = await client.post(
                "/review/cases",
                headers={**headers, IDEMPOTENCY_KEY_HEADER: "case-key-1"},
                files={"file": ("invoice.png", _png_bytes(), "image/png")},
            )
            case_id = created.json()["case_id"]

            responses = await asyncio.gather(
                *(
                    client.put(
                        f"/review/cases/{case_id}/assignment",
                        headers={**headers, IDEMPOTENCY_KEY_HEADER: f"claim-{index}"},
                        json={"expected_version": 1},
                    )
                    for index in range(5)
                )
            )
    finally:
        app.dependency_overrides.clear()

    statuses = sorted(response.status_code for response in responses)
    assert statuses.count(200) == 1
    assert statuses.count(409) == 4
    final = repository.get_case(case_id)
    assert final is not None
    assert final.version == 2


@pytest.mark.anyio
async def test_backup_and_restore_preserve_a_case_created_through_the_api(
    tmp_path: Path,
) -> None:
    database_path = tmp_path / "review.sqlite"
    repository = SQLiteReviewRepository(database_path)
    repository.initialize()
    app.dependency_overrides[get_review_repository] = lambda: repository
    app.dependency_overrides[get_review_actor_directory] = _directory
    app.dependency_overrides[get_review_origin_settings] = lambda: ReviewOriginSettings(
        origin=_ORIGIN
    )
    app.dependency_overrides[get_processing_service] = lambda: _FakeProcessingService(
        invoice_number="INV-777"
    )

    transport = httpx.ASGITransport(app=app)
    try:
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            headers = await _login(client)
            created = await client.post(
                "/review/cases",
                headers={**headers, IDEMPOTENCY_KEY_HEADER: "case-key-1"},
                files={"file": ("invoice.png", _png_bytes(), "image/png")},
            )
            case_id = created.json()["case_id"]
    finally:
        app.dependency_overrides.clear()

    backup_path = tmp_path / "review-backup.sqlite"
    backup_database(database_path, backup_path)

    repository.assign_case(
        case_id,
        request=CaseAssignmentRequest(expected_version=1),
        actor_id="reviewer-1",
        actor_role="reviewer",
        request_id="request-assign",
        idempotent_request=None,
    )
    mutated = repository.get_case(case_id)
    assert mutated is not None
    assert mutated.status == "assigned"

    restored_path = tmp_path / "review-restored.sqlite"
    restore_database(backup_path, restored_path)

    restored_repository = SQLiteReviewRepository(restored_path)
    restored_case = restored_repository.get_case(case_id)
    assert restored_case is not None
    assert restored_case.status == "unassigned"
    assert restored_case.snapshot.result.extraction.invoice_number == "INV-777"
