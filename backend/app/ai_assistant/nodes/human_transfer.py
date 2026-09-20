"""human_transfer node: escalate with context, never counsel."""
from __future__ import annotations


async def run(state: dict) -> dict:
    rt = state.get("_runtime", {}) or {}
    db = rt.get("db")
    user = rt.get("user")
    corr = rt.get("corr", "")
    from app.ai_assistant.mcp import adapter

    safety = state.get("safety") or {}
    summary = (f"Escalation ({safety.get('reason_category', 'escalated')}): "
               f"intent={state.get('intent')} classification={state.get('classification')}")
    out = await adapter.call(
        db, "transfer_to_human",
        {"summary": summary[:2000], "reason": safety.get("reason_category", "escalated")},
        user=user, conversation_id=state.get("conversation_id"), corr=corr)
    data = out.get("data", {}) if isinstance(out.get("data"), dict) else {}
    trace = [*state.get("trace", []), "transfer:care_team"]
    return {"transfer": {"escalated": True, "queue": "care_team",
                         "summary": summary, **data},
            "trace": trace}
