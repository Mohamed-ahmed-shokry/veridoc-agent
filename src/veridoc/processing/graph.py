"""The Phase 5 typed complete invoice-processing LangGraph flow."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from veridoc.explanation.graph import build_explanation_graph
from veridoc.explanation.models import ExplanationResult
from veridoc.explanation.service import ExplanationService
from veridoc.extraction.graph import build_extraction_graph
from veridoc.extraction.models import InvoiceExtraction
from veridoc.extraction.protocol import (
    ExtractionProcessingError,
    ExtractionRequest,
    StructuredExtractor,
)
from veridoc.ingestion.models import ValidatedUpload
from veridoc.ocr.models import OCRDocumentBundle
from veridoc.ocr.protocol import OCREngine
from veridoc.ocr.service import OCRService
from veridoc.processing.models import ProcessingResult, ProcessingVerdict
from veridoc.processing.verdict import derive_verdict
from veridoc.verification.graph import build_verification_graph
from veridoc.verification.models import VerificationResult
from veridoc.verification.service import VerificationService


class ProcessingState(TypedDict):
    """Typed state exchanged across the complete Phase 5 workflow."""

    upload: ValidatedUpload
    ocr: NotRequired[OCRDocumentBundle]
    extraction: NotRequired[InvoiceExtraction]
    verification: NotRequired[VerificationResult]
    explanations: NotRequired[ExplanationResult]
    verdict: NotRequired[ProcessingVerdict]
    result: NotRequired[ProcessingResult]


class _VerdictUpdate(TypedDict):
    verdict: ProcessingVerdict
    result: ProcessingResult


def build_processing_graph(
    ocr_engine: OCREngine,
    extractor: StructuredExtractor,
    verification_service: VerificationService,
    explanation_service: ExplanationService,
) -> CompiledStateGraph[ProcessingState]:
    """Compile OCR through verdict while reusing each phase's typed graph."""
    extraction_graph = build_extraction_graph(extractor)
    verification_graph = build_verification_graph(verification_service)
    explanation_graph = build_explanation_graph(explanation_service)

    def run_ocr(state: ProcessingState) -> dict[str, OCRDocumentBundle]:
        return {"ocr": OCRService(ocr_engine).process_with_page_images(state["upload"])}

    async def extract(
        state: ProcessingState,
    ) -> dict[str, InvoiceExtraction]:
        bundle = state["ocr"]
        extraction_state = await extraction_graph.ainvoke(
            {
                "request": ExtractionRequest(
                    document=bundle.document,
                    page_images=bundle.page_images,
                )
            }
        )
        extraction = extraction_state.get("extraction")
        if not isinstance(extraction, InvoiceExtraction):
            raise ExtractionProcessingError
        return {"extraction": extraction}

    def verify(state: ProcessingState) -> dict[str, VerificationResult]:
        verification_state = verification_graph.invoke(
            {"extraction": state["extraction"]}
        )
        verification = verification_state.get("verification")
        if not isinstance(verification, VerificationResult):
            raise TypeError("Verification graph did not return a typed result.")
        return {"verification": verification}

    async def explain(state: ProcessingState) -> dict[str, ExplanationResult]:
        explanation_state = await explanation_graph.ainvoke(
            {"verification": state["verification"]}
        )
        explanations = explanation_state.get("explanations")
        if not isinstance(explanations, ExplanationResult):
            raise TypeError("Explanation graph did not return a typed result.")
        return {"explanations": explanations}

    def determine_verdict(state: ProcessingState) -> _VerdictUpdate:
        verification = state["verification"]
        verdict = derive_verdict(verification)
        return {
            "verdict": verdict,
            "result": ProcessingResult(
                extraction=state["extraction"],
                findings=verification.findings,
                explanations=state["explanations"].explanations,
                verdict=verdict,
            ),
        }

    graph = StateGraph(ProcessingState)
    graph.add_node("ocr", run_ocr)
    graph.add_node("extract", extract)
    graph.add_node("verify", verify)
    graph.add_node("explain", explain)
    graph.add_node("verdict", determine_verdict)
    graph.add_edge(START, "ocr")
    graph.add_edge("ocr", "extract")
    graph.add_edge("extract", "verify")
    graph.add_edge("verify", "explain")
    graph.add_edge("explain", "verdict")
    graph.add_edge("verdict", END)
    return graph.compile()
