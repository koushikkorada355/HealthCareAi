"""Conversation node: continuity first.

Loads bounded history, appends the current turn, and prepares the model
context window. Writes nothing (the service layer persists messages).
"""
from __future__ import annotations

from .. import config
from ..context import manager as ctx_manager


async def run(state: dict) -> dict:
    rt = state.get("_runtime", {}) or {}
    db = rt.get("db")
    conversation_id = state.get("conversation_id") or rt.get("conversation_id") or 0
    text = state.get("messages", [{}])[-1].get("content", "") if state.get("messages") else rt.get("text", "")

    history: list[dict] = []
    if db is not None and conversation_id:
        history = ctx_manager.load_history(db, conversation_id)
    # The current turn is not yet persisted; include it for downstream nodes.
    if text:
        history = [*history, {"role": "user", "content": text}]

    summary = state.get("conversation_summary", "")
    if ctx_manager.needs_summary(len(history)) and not summary:
        pending = state.get("pending_clarification") or ""
        summary = await ctx_manager.summarize(history, pending or None, rt.get("llm"))

    window = history[-config.HISTORY_WINDOW:]
    return {
        "messages": window,
        "history_text": ctx_manager.history_text(window),
        "conversation_summary": summary,
        "trace": [*state.get("trace", []), f"conversation: history={len(window)}"],
    }
