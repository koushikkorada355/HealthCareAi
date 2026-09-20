"""memory node: LLM importance gate; rewrite summary only when important."""
from __future__ import annotations

import json


async def run(state: dict) -> dict:
    rt = state.get("_runtime", {}) or {}
    db = rt.get("db")
    from app.ai_assistant.services import llm as llm_mod
    from app.models import AIContext, AIMessage

    try:
        important = await llm_mod.importance_gate(
            state.get("conversation_summary", ""),
            [m.get("content", "") for m in (state.get("messages", []) or [])[-3:]])
    except Exception:
        raise
    trace = [*state.get("trace", []), f"memory:{'important' if important else 'skip'}"]
    if not important:
        return {"trace": trace}
    rows = (db.query(AIMessage).filter(
        AIMessage.conversation_id == state.get("conversation_id"))
        .order_by(AIMessage.id.desc()).limit(3).all())
    new_summary = await llm_mod.rewrite_summary(
        state.get("conversation_summary", ""),
        [r.content for r in reversed(rows)])
    ctx = db.query(AIContext).filter(
        AIContext.conversation_id == state.get("conversation_id")).first()
    if ctx:
        try:
            cur = json.loads(ctx.conversational or "{}")
        except Exception:
            cur = {}
        cur["summary"] = new_summary[:1200]
        ctx.conversational = json.dumps(cur)
        db.commit()
    out = {"conversation_summary": new_summary[:1200], "trace": trace}
    if state.get("intent") in ("book", "reschedule", "cancel", "lookup",
                               "questionnaire", "admin_q", "ambiguous"):
        try:
            prior_tx = {}
            if ctx:
                try:
                    prior_tx = json.loads(ctx.transactional or "{}")
                except Exception:
                    prior_tx = {}
            merged = await llm_mod.extract_entities(
                [r.content for r in reversed(rows)], prior_tx)
            if ctx and merged != prior_tx:
                ctx.transactional = json.dumps(merged)
                db.commit()
            out["context_refs"] = {**(state.get("context_refs") or {}),
                                   "transactional": merged}
        except Exception:
            pass
    return out
