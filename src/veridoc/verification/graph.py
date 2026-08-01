"""The Phase 3 typed LangGraph verification flow."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from veridoc.extraction.models import InvoiceExtraction
from veridoc.verification.models import VerificationResult
from veridoc.verification.service import VerificationService


class VerificationState(TypedDict):
    """Typed state exchanged by the Phase 3 verification graph."""

    extraction: InvoiceExtraction
    verification: NotRequired[VerificationResult]


def build_verification_graph(service: VerificationService):
    """Compile the single-node graph for deterministic invoice verification."""

    def verify(state: VerificationState) -> dict[str, VerificationResult]:
        return {"verification": service.verify(state["extraction"])}

    graph = StateGraph(VerificationState)
    graph.add_node("verify", verify)
    graph.add_edge(START, "verify")
    graph.add_edge("verify", END)
    return graph.compile()
