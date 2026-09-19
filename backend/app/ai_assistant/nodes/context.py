"""Context node: separate conversation context from application context.

- Conversation context: prior slices (intent/specialty/city/doctor/date),
  unresolved clarification, user prefs.
- Application context: entity references + verified tool outputs only.
  Nothing is invented here; application truth arrives via MCP tools later.

Reads AIContext + UserContextPref. Writes nothing.
"""
from __future__ import annotations

import json


_PRIOR_KEYS = ("intent", "specialty", "city", "hospital_id", "doctor_id", "date_pref")


def _load_json(raw: str | None) -> dict:
    try:
        parsed = json.loads(raw or "{}")
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


async def run(state: dict) -> dict:
    rt = state.get("_runtime", {}) or {}
    db = rt.get("db")
    conversation_id = state.get("conversation_id") or rt.get("conversation_id") or 0
    user = rt.get("user")

    refs: dict = {}
    if db is not None and conversation_id:
        try:
            from app import models

            ctx = (
                db.query(models.AIContext)
                .filter(models.AIContext.conversation_id == conversation_id)
                .first()
            )
            if ctx is not None:
                conv = _load_json(ctx.conversational)
                refs.update({k: conv[k] for k in _PRIOR_KEYS if conv.get(k) is not None})
                if user is not None:
                    pref = (
                        db.query(models.UserContextPref)
                        .filter(models.UserContextPref.user_id == user.id)
                        .first()
                    )
                    if pref is not None:
                        refs["prefs"] = _load_json(pref.prefs)
        except Exception:
            pass
    # Carry forward in-state refs (e.g. just-stored city/doctor from tool turns).
    for k, v in (state.get("context_refs") or {}).items():
        refs.setdefault(k, v)
    out: dict = {
        "context_refs": refs,
        "trace": [*state.get("trace", []), f"context: refs={sorted(refs)}"],
    }
    # Restore an unconsumed booking confirmation across HTTP turns.
    pending = refs.get("_pending")
    if isinstance(pending, dict) and pending.get("tool") and not state.get("pending_confirmation"):
        out["pending_confirmation"] = {k: v for k, v in pending.items() if k in ("tool", "args", "idempotency_key", "summary")}
        out["trace"].append("context: pending restored")
    return out
