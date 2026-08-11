"""The Phase 2 typed LangGraph extraction flow."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from veridoc.extraction.models import EvidenceReference, InvoiceExtraction
from veridoc.extraction.protocol import (
    ExtractionProcessingError,
    ExtractionRequest,
    StructuredExtractor,
)


class ExtractionState(TypedDict):
    """Typed state exchanged by the Phase 2 extraction graph."""

    request: ExtractionRequest
    extraction: NotRequired[InvoiceExtraction]


def build_extraction_graph(
    extractor: StructuredExtractor,
) -> CompiledStateGraph[ExtractionState]:
    """Compile the single-node graph for one structured extraction request."""

    async def extract(state: ExtractionState) -> dict[str, InvoiceExtraction]:
        request = state["request"]
        extraction = await extractor.extract(request)
        if not _evidence_pages_are_valid(
            extraction,
            page_count=len(request.document.pages),
        ):
            raise ExtractionProcessingError
        return {"extraction": extraction}

    graph = StateGraph(ExtractionState)
    graph.add_node("extract", extract)
    graph.add_edge(START, "extract")
    graph.add_edge("extract", END)
    return graph.compile()


def _evidence_pages_are_valid(
    extraction: InvoiceExtraction, *, page_count: int
) -> bool:
    references: list[EvidenceReference] = [
        reference
        for field_references in extraction.evidence.values()
        for reference in field_references
    ]
    references.extend(
        reference
        for line_item in extraction.line_items
        for reference in line_item.evidence
    )
    return all(reference.page_number <= page_count for reference in references)
