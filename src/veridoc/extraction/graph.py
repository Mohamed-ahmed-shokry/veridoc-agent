"""The Phase 2 typed LangGraph extraction flow."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph
from langgraph.graph.state import CompiledStateGraph

from veridoc.extraction.models import InvoiceExtraction
from veridoc.extraction.protocol import ExtractionRequest, StructuredExtractor


class ExtractionState(TypedDict):
    """Typed state exchanged by the Phase 2 extraction graph."""

    request: ExtractionRequest
    extraction: NotRequired[InvoiceExtraction]


def build_extraction_graph(
    extractor: StructuredExtractor,
) -> CompiledStateGraph[ExtractionState]:
    """Compile the single-node graph for one structured extraction request."""

    async def extract(state: ExtractionState) -> dict[str, InvoiceExtraction]:
        return {"extraction": await extractor.extract(state["request"])}

    graph = StateGraph(ExtractionState)
    graph.add_node("extract", extract)
    graph.add_edge(START, "extract")
    graph.add_edge("extract", END)
    return graph.compile()
