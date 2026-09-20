"""Assistant service: runs the 11-node graph with request-scoped runtime."""
from __future__ import annotations


async def run_turn(db, *, user, conversation_id: int | None, text: str,
                   channel: str = "web", corr: str = "") -> dict:
    from app.ai_assistant.graph.graph import get_graph
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
    graph = get_graph()
    state = {"channel": channel, "_runtime": {
        "db": db, "user": user, "text": text,
        "conversation": conv, "corr": corr,
        "max_hops": settings.LLM_MAX_HOPS, "window": settings.AI_SHORT_WINDOW}}
    try:
        out = await graph.ainvoke(state, config={"configurable": {"thread_id": f"conv-{conv.id if conv else 'new'}"}})
    except AINotAvailable:
        raise
    return {"reply": out.get("reply", ""), "conversation_id": out.get("conversation_id"),
            "correlation_id": corr, "trace": out.get("trace", []),
            "data": out.get("data", {}), "powered_by": out.get("powered_by", "")}
