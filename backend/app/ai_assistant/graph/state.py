"""Strongly-typed LangGraph state for the AI Assistant Layer (§4).

Only workflow-carried information lives here — never authoritative
application state. The application database remains the source of truth;
state holds references (ids) plus verified tool outputs for reply building.

`_runtime` carries non-serializable request context (DB session, user ORM
object, ids, channel) for node use. It is never persisted and never sent
to any model.
"""
from typing import Any, TypedDict


class AssistantState(TypedDict, total=False):
    # Identity / session.
    conversation_id: int
    user_id: int
    channel: str
    graph_run_id: str
    # Conversation handling.
    messages: list[dict[str, str]]
    # [{role, content}] bounded window for the model.
    history_text: str
    conversation_summary: str
    # Understanding.
    intent: str
    classification: dict[str, Any]
    safety: dict[str, str]
    # {"verdict","reason_category"}
    # Context references (ids + prior slices, never bulk records).
    context_refs: dict[str, Any]
    pending_clarification: str
    # Tool routing.
    selected_tool: str
    tool_args: dict[str, Any]
    pending_confirmation: dict[str, Any]
    # {tool,args,idempotency_key,summary} or {}.
    tool_result: dict[str, Any]
    tool_status: str
    # ok|failed|denied|timeout|skipped.
    tool_call_id: str
    # Escalation.
    transfer: dict[str, Any]
    # {escalated, queue, summary} or {}.
    # Output.
    reply: str
    trace: list[str]
    data: dict[str, Any]
    powered_by: str
    # Internal runtime (db session, user object, corr). Not persisted/sent.
    _runtime: dict[str, Any]
