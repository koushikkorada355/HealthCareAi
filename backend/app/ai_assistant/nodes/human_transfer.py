"""Human-transfer node: preserve context, hand off, invent nothing.

Invokes the existing transfer_to_human capability (audited like any tool)
so the escalation is recorded, then stores the operator handoff summary.
Falls back to record-only if invocation fails — the handoff summary still
reaches the operator through state/trace.
"""
from __future__ import annotations


async def run(state: dict) -> dict:
    from ..mcp import adapter, client

    rt = state.get("_runtime", {}) or {}
    classification = state.get("classification") or {}
    refs = state.get("context_refs") or {}
    safety = state.get("safety") or {}
    summary = (
        "Handoff to human operator. "
        f"Intent: {state.get('intent') or classification.get('intent', 'unknown')}. "
        f"Entities: {sorted([k for k, v in refs.items() if v not in (None, '')]) or 'none'}. "
        f"Safety: {safety.get('verdict', 'allow')}/{safety.get('reason_category', '')}. "
        f"Run: {state.get('graph_run_id', '')}."
    )
    trace = list(state.get("trace", []))
    db, user = rt.get("db"), rt.get("user")
    if db is not None and user is not None:
        try:
            out = await adapter.call(
                db, "transfer_to_human",
                {"reason": f"assistant handoff ({safety.get('reason_category', 'escalated')})",
                 "hospital_id": refs.get("hospital_id")}, user=user,
                conversation_id=state.get("conversation_id") or rt.get("conversation_id"),
                corr=rt.get("corr", ""), tool_call_id=client.new_tool_call_id())
            trace.append(f"transfer: {out.get('code')}")
        except Exception:
            trace.append("transfer: record-only (invoke failed)")
    return {
        "transfer": {"escalated": True, "queue": "care-ops", "summary": summary},
        "trace": [*trace, "transfer: handoff recorded"],
    }

