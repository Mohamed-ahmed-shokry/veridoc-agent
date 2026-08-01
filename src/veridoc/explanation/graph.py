"""The Phase 4 typed LangGraph explanation flow."""

from __future__ import annotations

from typing import NotRequired, TypedDict

from langgraph.graph import END, START, StateGraph

from veridoc.explanation.models import ExplanationResult
from veridoc.explanation.service import ExplanationService
from veridoc.verification.models import VerificationResult


class ExplanationState(TypedDict):
    """Typed state exchanged by the Phase 4 explanation graph."""

    verification: VerificationResult
    explanations: NotRequired[ExplanationResult]


def build_explanation_graph(service: ExplanationService):
    """Compile the single-node graph for evidence-grounded explanations."""

    async def explain(state: ExplanationState) -> dict[str, ExplanationResult]:
        return {"explanations": await service.explain(state["verification"])}

    graph = StateGraph(ExplanationState)
    graph.add_node("explain", explain)
    graph.add_edge(START, "explain")
    graph.add_edge("explain", END)
    return graph.compile()
