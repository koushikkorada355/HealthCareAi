"""Assistant service: one conversational turn through the graph.

Owns the request lifecycle the route used to inline: conversation row,
context load (via nodes), user/assistant message writes, conversational
slice persistence (6-key discipline + pending confirmation), and
observability IDs. Never invents application state; tools do the work.
"""
from __future__ import annotations

import json
import logging
import uuid

logger = logging.getLogger("careaccess.assistant")

_PERSIST_KEYS = ("intent", "specialty", "city", "hospital_id", "doctor_id", "date_pref")

from ..graph.graph import get_graph
from ..graph.state import AssistantState
from .llm import get_llm


def _new_id() -> str:
    return uuid.uuid4().hex[:12]


async def run_turn(db, user, body: dict) -> dict:
    """Run one turn. Returns the public chat envelope (legacy-compatible)."""
    from app import models
    from app.core.correlation import new_corr

    text = (body.get("message") or "").strip()
    corr = body.get("correlation_id") or new_corr()
    graph_run_id = _new_id()
    conv_id = body.get("conversation_id")
    channel = body.get("channel", "web") or "web"

    conv = db.query(models.AIConversation).filter(models.AIConversation.id == conv_id).first() if conv_id else None
    if not conv:
        conv = models.AIConversation(user_id=user.id, hospital_id=user.hospital_id,
                                     channel=channel, status="active", correlation_id=corr)
        db.add(conv); db.commit(); db.refresh(conv)
        db.add(models.AIContext(conversation_id=conv.id)); db.commit()

    llm = get_llm()
    db.add(models.AIMessage(conversation_id=conv.id, role="user", content=text)); db.commit()

    initial: AssistantState = {
        "conversation_id": conv.id, "user_id": user.id, "channel": channel,
        "graph_run_id": graph_run_id,
        "messages": [{"role": "user", "content": text}],
        "trace": [f"run:{graph_run_id}", f"corr:{corr}"],
        "data": {}, "powered_by": "rules",
        "_runtime": {"db": db, "user": user, "conversation_id": conv.id,
                     "corr": corr, "channel": channel, "text": text, "llm": llm},
    }
    try:
        out = await get_graph().ainvoke(initial)
    except Exception:
        logger.exception("assistant graph failed run=%s conv=%s", graph_run_id, conv.id)
        raise

    reply = out.get("reply") or "I can help with appointments and admin tasks. What would you like to do?"
    powered = out.get("powered_by", "rules")
    trace = list(out.get("trace", []))
    data = dict(out.get("data") or {})
    data.setdefault("graph_run_id", graph_run_id)
    safety = dict(out.get("safety") or {"verdict": "allow", "reason_category": ""})

    # Persist conversational slice (6-key discipline) + pending confirmation.
    try:
        ctx = db.query(models.AIContext).filter(models.AIContext.conversation_id == conv.id).first()
        refs = dict(out.get("context_refs") or {})
        saved = {k: refs[k] for k in _PERSIST_KEYS if refs.get(k) is not None}
        if out.get("intent"):
            saved["intent"] = out["intent"]
        pending = out.get("pending_confirmation") or {}
        if pending.get("tool"):
            saved["_pending"] = {k: pending[k] for k in ("tool", "args", "idempotency_key", "summary") if k in pending}
        if ctx is None:
            ctx = models.AIContext(conversation_id=conv.id)
            db.add(ctx)
        ctx.conversational = json.dumps(saved)
        db.commit()
    except Exception:
        logger.exception("assistant slice persist failed run=%s", graph_run_id)

    db.add(models.AIMessage(conversation_id=conv.id, role="assistant", content=reply)); db.commit()
    logger.info("assistant turn run=%s conv=%s intent=%s tool=%s status=%s",
                graph_run_id, conv.id, out.get("intent"),
                out.get("selected_tool"), out.get("tool_status"))

    classification = out.get("classification") or {}
    return {
        "conversation_id": conv.id,
        "correlation_id": corr,
        "intent": out.get("intent") or classification.get("intent", "unknown"),
        "route": _legacy_route(out),
        "reply": reply,
        "trace": trace,
        "data": {**data, **_legacy_data(out)},
        "powered_by": powered,
        "graph_run_id": graph_run_id,
        "safety": {"verdict": safety.get("verdict", "allow"),
                   "reason_category": safety.get("reason_category", "")},
    }


def _legacy_route(out: dict) -> str:
    """Keep the old route vocabulary for existing clients/traces."""
    intent = out.get("intent", "unknown")
    if out.get("selected_tool"):
        return "discover"
    if out.get("pending_clarification"):
        return "clarify"
    if out.get("pending_confirmation", {}).get("tool"):
        return "clarify"
    return {"find_hospital": "discover_hospitals", "book": "discover",
            "find_doctor": "discover"}.get(intent, "answer")


def _legacy_data(out: dict) -> dict:
    data = dict(out.get("data") or {})
    result = out.get("tool_result") or {}
    if isinstance(result.get("data"), dict):
        for k in ("doctors", "slots", "hospitals", "hospital", "doctor"):
            if k in result["data"]:
                data.setdefault(k, result["data"][k])
    return data
