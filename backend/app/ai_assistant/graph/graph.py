"""Graph composition: explicit workflow, explicit routing.

Node implementations live in nodes/. This module only composes them and
declares conditional edges — no business logic here.

Flow:
  conversation -> context -> classification -> safety -+-> human_transfer -+
    |  allow                                          |deny(other)      |escalate
    v                                                 v                 v
  scope -> clarification -> tool_router -> tool_result -> response -> END
     unrelated/         |missing info      |no tool
     unsupported        v                  v
                   response             response
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from ..nodes import (
    clarification,
    classification,
    context,
    conversation,
    human_transfer,
    response,
    safety,
    scope,
    tool_result,
    tool_router,
)
from .state import AssistantState


def build_graph():
    """Compile the assistant graph. Raises on structural errors (fail fast)."""
    g = StateGraph(AssistantState)
    g.add_node("conversation", conversation.run)
    g.add_node("context", context.run)
    g.add_node("classify", classification.run)
    g.add_node("safety_check", safety.run)
    g.add_node("scope", scope.run)
    g.add_node("clarification", clarification.run)
    g.add_node("tool_router", tool_router.run)
    g.add_node("result", tool_result.run)
    g.add_node("human_transfer", human_transfer.run)
    g.add_node("response", response.run)

    g.set_entry_point("conversation")
    g.add_edge("conversation", "context")
    g.add_edge("context", "classify")
    g.add_edge("classify", "safety_check")
    g.add_conditional_edges("safety_check", safety.route_after_safety,
                            {"scope": "scope", "response": "response",
                             "human_transfer": "human_transfer"})
    g.add_conditional_edges("scope", scope.route_after_scope,
                            {"clarification": "clarification", "response": "response"})
    g.add_conditional_edges("clarification", clarification.route_after_clarification,
                            {"tool_router": "tool_router", "response": "response"})
    g.add_conditional_edges("tool_router", tool_router.route_after_router,
                            {"result": "result", "response": "response"})
    g.add_edge("result", "response")
    g.add_edge("human_transfer", "response")
    g.add_edge("response", END)
    return g.compile()


_GRAPH = None


def get_graph():
    """Lazily compiled singleton (mirrors the existing layer's pattern)."""
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH
