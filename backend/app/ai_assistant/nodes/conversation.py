"""conversation node: persist user turn, hydrate short-term window."""
from __future__ import annotations

import json
import time


async def run(state: dict) -> dict:
    rt = state.get("_runtime", {}) or {}
    db = rt.get("db")
    user = rt.get("user")
    text = rt.get("text", "")
    conv = rt.get("conversation")
    corr = rt.get("corr", "")
    t0 = time.time()
    from app.models import AIConversation, AIMessage, AIContext

    if conv is None:
        conv = AIConversation(user_id=user.id,
                              hospital_id=getattr(user, "hospital_id", None),
                              channel=state.get("channel", "web"), correlation_id=corr)
        db.add(conv)
        db.commit()
        db.refresh(conv)
        db.add(AIContext(conversation_id=conv.id))
        db.commit()
    db.add(AIMessage(conversation_id=conv.id, role="user", content=text[:4000],
                     latency_ms=int((time.time() - t0) * 1000)))
    db.commit()
    from app.core.config import settings

    window = settings.AI_SHORT_WINDOW
    rows = (db.query(AIMessage).filter(AIMessage.conversation_id == conv.id)
            .order_by(AIMessage.id.desc()).limit(window * 3).all())
    rows = list(reversed(rows))[-window:]
    messages = []
    for r in rows:
        # OpenAI-format APIs require tool_call_id on role=tool messages, which
        # our stored rows don't carry — surface them as system context instead.
        if r.role == "tool":
            messages.append({"role": "system",
                             "content": f"[tool:{r.tool_name or 'result'}] {r.content}"})
        else:
            messages.append({"role": r.role, "content": r.content})
    history_text = "\n".join(f"{m['role']}: {m['content'][:500]}" for m in messages)
    ctx = db.query(AIContext).filter(AIContext.conversation_id == conv.id).first()
    summary = ""
    if ctx:
        try:
            summary = (json.loads(ctx.conversational or "{}").get("summary", ""))
        except Exception:
            summary = ""
    trace = [*state.get("trace", []), f"conversation:{conv.id}"]
    return {"conversation_id": conv.id, "user_id": user.id, "messages": messages,
            "history_text": history_text, "conversation_summary": summary,
            "hop_count": 0, "trace": trace}
