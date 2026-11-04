"""Assistant service: runs the graph with request-scoped runtime.

State persistence across turns uses a LangGraph checkpointer (Postgres when
available, in-memory fallback) keyed by thread_id == conversation id, so
multi-step plans, pending approvals and execution state resume correctly.
Falls back to a stateless graph if no checkpointer is available.
"""
from __future__ import annotations


_GRAPH_BY_CHECKPOINTER: dict = {}


async def run_turn(db, *, user, conversation_id: int | None, text: str,
                   channel: str = "web", corr: str = "") -> dict:
    from app.ai_assistant.graph.graph import build_graph
    from app.ai_assistant.services.llm import AINotAvailable
    from app.core.config import settings
    from app.models import AIConversation

    conv = None
    if conversation_id:
        conv = db.query(AIConversation).filter(AIConversation.id == int(conversation_id)).first()
        if not conv:
            raise ValueError("Conversation not found")
        if getattr(user, "role", "") == "patient" and conv.user_id != user.id:
            raise PermissionError("Not your conversation")
        if (getattr(user, "role", "") in ("hospital_admin", "doctor")
                and conv.hospital_id and getattr(user, "hospital_id", None)
                and int(conv.hospital_id) != int(user.hospital_id)):
            raise PermissionError("Cross-tenant denied")
    graph = _get_graph()
    state = {"channel": channel, "_runtime": {
        "db": db, "user": user, "text": text,
        "conversation": conv, "corr": corr,
        "max_hops": settings.LLM_MAX_HOPS, "window": settings.AI_SHORT_WINDOW}}
    try:
        out = await graph.ainvoke(state, config={"configurable": {"thread_id": f"conv-{conv.id if conv else 'new'}"}})
    except AINotAvailable:
        raise
    # Post-guard (generic): never return a success claim when the tool did
    # not succeed, even if the response node hallucinated one.
    try:
        from app.ai_assistant.nodes.response import _claims_success, sanitize_reply
        _tres = out.get("tool_result") or {}
        _tok = bool(_tres.get("ok"))
        _rep = str(out.get("reply", ""))
        if _claims_success(_rep) and not _tok:
            _rep = sanitize_reply(_rep, tool_ok=False, data={})
            if _claims_success(_rep):
                _rep = "I couldn't complete that. Could you share a bit more detail so I can help?"
            out["reply"] = _rep
    except Exception:
        pass
    return {"reply": out.get("reply", ""), "conversation_id": out.get("conversation_id"),
            "correlation_id": corr, "trace": out.get("trace", []),
            "data": out.get("data", {}), "powered_by": out.get("powered_by", "")}


def _get_graph():
    """Cached graph bound to the best available checkpointer."""
    from app.ai_assistant.graph.graph import build_graph

    try:
        from app.ai_assistant.checkpointer import get_checkpointer
        checkpointer, _needs_setup = get_checkpointer()
        if _needs_setup:
            try:
                checkpointer.setup()
            except Exception:
                checkpointer = None
        key = type(checkpointer).__name__ if checkpointer is not None else "none"
    except Exception:
        checkpointer, key = None, "none"
    if key not in _GRAPH_BY_CHECKPOINTER:
        try:
            _GRAPH_BY_CHECKPOINTER[key] = build_graph(checkpointer=checkpointer)
        except Exception:
            _GRAPH_BY_CHECKPOINTER[key] = build_graph()
    return _GRAPH_BY_CHECKPOINTER[key]
