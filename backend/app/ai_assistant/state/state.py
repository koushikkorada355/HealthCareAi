"""AssistantState: workflow-carried info only, never authoritative app state.

DB tables (ai_conversations/messages/contexts) are the source of truth.
_runtime carries the request-scoped DB session/user/corr — never persisted,
never sent to the LLM.
"""
from __future__ import annotations

from typing import Any, TypedDict


class AssistantState(TypedDict, total=False):
    conversation_id: int
    user_id: int
    channel: str
    messages: list[dict[str, str]]
    history_text: str
    conversation_summary: str
    intent: str
    classification: dict[str, Any]
    safety: dict[str, str]
    context_refs: dict[str, Any]
    scope_hint: str
    pending_clarification_fields: list[str]
    selected_tool: str
    tool_args: dict[str, Any]
    plan_steps: list[dict[str, Any]]
    plan_active: bool
    missing_tool: dict[str, Any]
    pending_confirmation: dict[str, Any]
    tool_result: dict[str, Any]
    tool_status: str
    tool_call_id: str
    step_outputs: list[dict[str, Any]]
    last_tool: str
    last_args: dict[str, Any]
    hop_count: int
    chain_hint: str
    transfer: dict[str, Any]
    reply: str
    trace: list[str]
    data: dict[str, Any]
    powered_by: str
    _runtime: dict[str, Any]
