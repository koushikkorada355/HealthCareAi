"""context node: load durable slices, never bulk records."""
from __future__ import annotations

import json


async def run(state: dict) -> dict:
    rt = state.get("_runtime", {}) or {}
    db = rt.get("db")
    user = rt.get("user")
    from app.models import AIContext, UserContextPref

    ctx = db.query(AIContext).filter(
        AIContext.conversation_id == state.get("conversation_id")).first()
    refs: dict = {}
    if ctx:
        for k in ("conversational", "transactional", "user_ctx", "workflow_state", "integration_state"):
            try:
                refs[k] = json.loads(getattr(ctx, k) or "{}")
            except Exception:
                refs[k] = {}
    pref = db.query(UserContextPref).filter(UserContextPref.user_id == user.id).first()
    if pref:
        try:
            refs["prefs"] = json.loads(pref.prefs or "{}")
        except Exception:
            refs["prefs"] = {}
    trace = [*state.get("trace", []), "context:loaded"]
    return {"context_refs": refs, "trace": trace}
