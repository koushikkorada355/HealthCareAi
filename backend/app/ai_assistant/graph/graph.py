"""Graph composition only — no business logic here.

conversation -> context -> classify -> safety_check -+-> human_transfer -> response -> memory -> END
                                              allow| |deny(other)      ^          |
                                               scope| v                |          v
                                               clarification -> tool_router ⇄ result
                                               (missing)  (no tool)———^    |
                                                  |________response <--------/
"""
from __future__ import annotations

from langgraph.graph import END, StateGraph

from app.ai_assistant.nodes import (
    clarification,
    classification,
    context,
    conversation,
    human_transfer,
    memory,
    response,
    safety,
    scope,
    tool_result,
    tool_router,
)
from app.ai_assistant.state.state import AssistantState


def build_graph(checkpointer=None):
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
    g.add_node("memory", memory.run)
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
    g.add_conditional_edges("result", tool_result.route_after_result,
                            {"tool_router": "tool_router", "response": "response"})
    g.add_edge("human_transfer", "response")
    g.add_edge("response", "memory")
    g.add_edge("memory", END)
    if checkpointer is not None:
        return g.compile(checkpointer=checkpointer)
    return g.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH
