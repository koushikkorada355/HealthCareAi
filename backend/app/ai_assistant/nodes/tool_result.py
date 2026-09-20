"""tool_result node: invoke via adapter, persist tool message, bump hops."""
from __future__ import annotations

import json
import time


async def run(state: dict) -> dict:
    rt = state.get("_runtime", {}) or {}
    db = rt.get("db")
    user = rt.get("user")
    corr = rt.get("corr", "")
    from app.ai_assistant.mcp import adapter
    from app.core.config import settings
    from app.models import AIMessage

    tool = state.get("selected_tool", "")
    args = state.get("tool_args", {})
    pending = state.get("pending_confirmation") or {}
    t0 = time.time()
    out = await adapter.call(
        db, tool, args, user=user, conversation_id=state.get("conversation_id"),
        idempotency_key=pending.get("idempotency_key", ""), corr=corr)
    hops = int(state.get("hop_count", 0)) + 1
    db.add(AIMessage(conversation_id=state.get("conversation_id"), role="tool",
                     content=json.dumps(out.get("data", {}))[:4000],
                     tool_name=tool, tool_call_id=out.get("tool_call_id", ""),
                     latency_ms=int((time.time() - t0) * 1000)))
    db.commit()
    status = "ok" if out.get("ok") else out.get("code", "failed")
    trace = [*state.get("trace", []), f"result:{tool}/{status}"]
    update: dict = {"tool_result": out, "tool_status": status,
                    "tool_call_id": out.get("tool_call_id", ""),
                    "hop_count": hops, "trace": trace,
                    "last_tool": tool, "last_args": args}
    if out.get("ok"):
        steps = list(state.get("step_outputs") or [])
        steps.append({"tool": tool, "data": out.get("data", {})})
        update["step_outputs"] = steps[-4:]
    if tool == state.get("last_tool"):
        # Same tool twice in a row never helps — answer with what we have.
        update["chain_hint"] = ""
        return update
    max_hops = settings.LLM_MAX_HOPS
    intent = state.get("intent", "")
    # Plan-driven flows chain via plan_steps (see route_after_result); the
    # heuristic below is only for single-tool LLM picks without a stored plan.
    # It fires only after SEARCH tools (search -> availability progression);
    # leaf tools (availability, lists, details) answer and stop.
    plan_active = bool(state.get("plan_steps")) or bool(state.get("plan_active"))
    if (out.get("ok") and hops < max_hops and not plan_active and intent in ("book", "reschedule")
            and tool in ("search_doctors", "search_hospitals", "get_doctor_details")):
        data = out.get("data", {}) if isinstance(out.get("data"), dict) else {}
        if not (data.get("appointment_id") or data.get("id") and tool in ("create_appointment",)):
            update["chain_hint"] = f"after {tool}: continue booking chain if data allows"
            update["selected_tool"] = ""
    else:
        update["chain_hint"] = ""
    return update


def route_after_result(state: dict) -> str:
    from app.core.config import settings

    if state.get("tool_status") != "ok":
        return "response"
    # Stored multi-step plan takes precedence over heuristics.
    if state.get("plan_steps") and int(state.get("hop_count", 0)) < settings.LLM_MAX_HOPS:
        return "tool_router"
    if (state.get("chain_hint") and int(state.get("hop_count", 0)) < settings.LLM_MAX_HOPS):
        return "tool_router"
    return "response"
