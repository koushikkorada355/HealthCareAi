"""tool_result: generic executor + evaluator. No tool names here.

Executes the router's selected step plus any parallel-ready batch, enforces
policy (approval / timeout / idempotency keys), persists each result, then
decides generically: more plan steps -> router, actionable data + hops left
-> router (chain), else response. Adding a tool changes nothing here.
"""
from __future__ import annotations

import asyncio
import json
import time
import uuid


async def _execute_one(db, user, conv_id, corr, tool, args, idem_key, timeout_s):
    from app.ai_assistant.mcp import adapter
    from app.ai_assistant.services import llm as llm_mod  # noqa: F401 (fail-closed import)

    t0 = time.time()
    try:
        out = await adapter.call(
            db, tool, args, user=user, conversation_id=conv_id,
            idempotency_key=idem_key, corr=corr, timeout_s=timeout_s)
    except Exception:
        raise  # fail-closed (e.g. AINotAvailable surfaces as 503, never guessed)
    return out, int((time.time() - t0) * 1000)


async def run(state: dict) -> dict:
    from app.ai_assistant import orchestration as orch
    from app.core.config import settings
    from app.models import AIMessage

    rt = state.get("_runtime", {}) or {}
    db, user, corr = rt.get("db"), rt.get("user"), rt.get("corr", "")
    conv_id = state.get("conversation_id")

    tool = state.get("selected_tool", "")
    args = state.get("tool_args", {})
    if not tool:
        return {"tool_result": {"ok": False, "code": "skipped"},
                "tool_status": "skipped",
                "trace": [*state.get("trace", []), "result:skipped"],
                "chain_hint": ""}
    pending = state.get("pending_confirmation") or {}
    idem_key = pending.get("idempotency_key", "") or uuid.uuid4().hex

    # deterministic approval gate (policy-driven, never LLM-decided)
    appr = state.get("pending_approval") or {}
    step_id = appr.get("step_id", "") if appr.get("tool") == tool else ""
    approved_ids = set(state.get("approved_step_ids") or [])
    if appr.get("tool") == tool and step_id not in approved_ids:
        trace = [*state.get("trace", []), f"result:approval-pending({tool})"]
        return {"tool_result": {"ok": False, "code": "approval_pending"},
                "tool_status": "approval_pending",
                "hop_count": int(state.get("hop_count", 0)),
                "trace": trace, "last_tool": tool, "last_args": args,
                "chain_hint": ""}

    batch = [{"tool": tool, "args": args, "idempotency_key": idem_key,
              "step_id": appr.get("step_id", "") if appr.get("tool") == tool else ""}]
    for extra in state.get("plan_batch") or []:
        if not isinstance(extra, dict) or not extra.get("tool"):
            continue
        if not orch.policy_for(extra["tool"]).get("parallel_safe", True):
            continue
        need, _ = orch.needs_approval(extra["tool"], extra.get("args", {}))
        if need and extra.get("id") not in approved_ids:
            continue
        batch.append({"tool": extra["tool"], "args": extra.get("args", {}),
                      "idempotency_key": uuid.uuid4().hex,
                      "step_id": extra.get("id", "")})

    async def _one(item):
        out, ms = await _execute_one(
            db, user, conv_id, corr, item["tool"], item["args"],
            item["idempotency_key"], orch.timeout_for(item["tool"]))
        return item, out, ms

    if len(batch) > 1:
        results = await asyncio.gather(*(_one(i) for i in batch))
    else:
        results = [await _one(batch[0])]

    completed_ids = set(state.get("completed_step_ids") or [])
    step_outs = list(state.get("step_outputs") or [])
    first_out = None
    for item, out, ms in results:
        try:
            keep = int(getattr(settings, "AI_STEP_KEEP", 4))
        except Exception:
            keep = 4
        db.add(AIMessage(conversation_id=conv_id, role="tool",
                         content=json.dumps(out.get("data", {}))[:4000],
                         tool_name=item["tool"], tool_call_id=out.get("tool_call_id", ""),
                         latency_ms=ms))
        if out.get("ok"):
            entry = {"tool": item["tool"], "data": out.get("data", {})}
            if item.get("step_id"):
                entry["step_id"] = item["step_id"]
                completed_ids.add(item["step_id"])
            step_outs.append(entry)
            step_outs = step_outs[-keep:]
        if item["tool"] == tool:
            first_out = out
    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    out = first_out or {"ok": False, "code": "failed"}
    hops = int(state.get("hop_count", 0)) + 1
    status = "ok" if out.get("ok") else out.get("code", "failed")
    try:
        from app.ai_assistant.mcp import outcomes as _oc
        outcome = _oc.derive_outcome(out, out.get("data", {}))
    except Exception:
        outcome = "failed" if not out.get("ok") else "unverified"
    trace = [*state.get("trace", []),
             f"result:{tool}/{status}/{outcome}" + (f"x{len(results)}" if len(results) > 1 else "")]
    update: dict = {"tool_result": out, "tool_status": status,
                    "tool_outcome": outcome,
                    "tool_call_id": out.get("tool_call_id", ""),
                    "hop_count": hops, "trace": trace,
                    "last_tool": tool, "last_args": args,
                    "step_outputs": step_outs,
                    "completed_step_ids": sorted(completed_ids),
                    "plan_batch": []}
    if tool == state.get("last_tool"):
        update["chain_hint"] = ""
        return update
    max_hops = settings.LLM_MAX_HOPS
    remaining = [s for s in (state.get("plan_steps") or [])
                 if s.get("id") not in completed_ids]
    if remaining:
        update["plan_steps"] = remaining
    plan_active = bool(remaining)
    # Chain only on verified success with actionable lists; unverified,
    # empty, partial, or failed results go to response for accurate messaging.
    if out.get("ok") and update.get("tool_outcome") in ("success",) and hops < max_hops and not plan_active \
            and orch.has_actionable_data(out.get("data", {})):
        update["chain_hint"] = f"after {tool}: continue with next global step if needed"
        update["selected_tool"] = ""
    else:
        update["chain_hint"] = ""
    return update


def route_after_result(state: dict) -> str:
    from app.core.config import settings

    if state.get("tool_status") == "approval_pending":
        return "response"
    if state.get("tool_status") != "ok":
        return "response"
    # Stored multi-step plan takes precedence over heuristics.
    remaining = [s for s in (state.get("plan_steps") or [])
                 if s.get("id") not in set(state.get("completed_step_ids") or [])] \
        if state.get("completed_step_ids") else (state.get("plan_steps") or [])
    if remaining and int(state.get("hop_count", 0)) < settings.LLM_MAX_HOPS:
        return "tool_router"
    if (state.get("chain_hint") and int(state.get("hop_count", 0)) < settings.LLM_MAX_HOPS):
        return "tool_router"
    return "response"
