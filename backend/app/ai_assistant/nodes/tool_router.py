"""tool_router: generic planner. LLM picks tools, code validates + resolves.

No tool names or per-tool branches here. The plan shape, catalog, schemas
and policies all come from ``mcp.registry`` via ``orchestration`` at runtime:
adding a new MCP tool requires zero changes in this file.
"""
from __future__ import annotations

import json
import uuid


async def run(state: dict) -> dict:
    from app.ai_assistant.mcp import adapter
    from app.ai_assistant import orchestration as orch
    from app.ai_assistant.prompts.system import ROUTER_SYSTEM
    from app.ai_assistant.services import llm as llm_mod
    from app.ai_assistant.utils.dates import normalize_global

    tools = adapter.known_tools()
    _names, catalog = orch.build_catalog()
    tx = (state.get("context_refs") or {}).get("transactional") or {}
    if isinstance(tx, str):
        try:
            tx = json.loads(tx)
        except Exception:
            tx = {}
    candidates = orch.collect_candidates(state)
    norm = normalize_global((state.get("classification") or {}), tx)
    completed = set(state.get("completed_step_ids") or [])

    pending = list(state.get("plan_steps") or [])
    if pending:
        # Continue a stored multi-step plan — no LLM call needed.
        ready = orch.ready_steps(pending, completed)
        if not ready:
            return _fail(state, {}, {"wanted": "plan",
                                     "reason": "plan deadlocked: no step has its dependencies met"})
        return _dispatch(state, ready, [s for s in pending if s not in ready],
                         tx, norm, candidates, completed)

    cls_d = state.get("classification", {}) or {}
    pend_appr = state.get("pending_approval")
    prompt = (
        f"Intent: {state.get('intent')}\n"
        f"Classification: {json.dumps(cls_d)[:1000]}\n"
        f"Summary: {state.get('conversation_summary', '')[:800]}\n"
        f"Context: {json.dumps(state.get('context_refs', {}))[:1500]}\n"
        f"Known entities: {json.dumps(tx)[:600]}\n"
        f"Normalized date: {json.dumps(norm)}\n"
        f"Candidates: {json.dumps(candidates)[:1200]}\n"
        f"Pending approval: {json.dumps(pend_appr)[:600] if pend_appr else 'none'}\n"
        f"History:\n{state.get('history_text', '')[-2000:]}\n"
        f"Chain: {state.get('chain_hint', '')}\n"
        "Plan globally (direct, multi-step, or unavailable). JSON only.")
    try:
        res = await llm_mod.generate(
            [{"role": "user", "content": prompt}],
            system=ROUTER_SYSTEM.replace("__CATALOG__", catalog))
        try:
            data = json.loads(res.content)
        except Exception:
            s, e = res.content.find("{"), res.content.rfind("}")
            data = json.loads(res.content[s:e + 1]) if s >= 0 and e > s else {}
    except Exception:
        raise
    raw = data.get("plan")
    if not isinstance(raw, list):
        t1, a1 = str(data.get("tool", "none")), data.get("args", {})
        raw = [{"tool": t1, "args": a1 if isinstance(a1, dict) else {}}] \
            if t1 not in ("", "none") else []
    if not raw:
        return _fail(state, {}, {"wanted": str(data.get("unavailable", "unknown")),
                                 "reason": "no capable tool",
                                 "alternatives": data.get("alternatives", [])})
    steps, err = orch.validate_plan(raw)
    if err:
        if err.get("wanted") in tools or err.get("wanted", "").startswith("step_"):
            return _fail(state, {}, err)
        return _fail(state, {}, {**err, "alternatives": data.get("alternatives", [])})
    if state.get("last_tool") and len(steps) == 1 and steps[0]["tool"] == state.get("last_tool") \
            and not state.get("step_outputs"):
        # Same single tool twice with no new output — answer with what we have.
        trace = [*state.get("trace", []), f"router:repeat({steps[0]['tool']})"]
        return {"selected_tool": "", "tool_args": {}, "plan_steps": [],
                "missing_tool": {"wanted": steps[0]["tool"],
                                 "reason": "already called this turn"},
                "chain_hint": "", "trace": trace}
    # Approval carry-over: planner re-emitted a pending step with approval.
    if pend_appr:
        for s in steps:
            if s["tool"] == pend_appr.get("tool") and s.get("approved"):
                _mark_approved(state, pend_appr.get("step_id", ""))
    ready = orch.ready_steps(steps, completed)
    if not ready:
        return _fail(state, {}, {"wanted": "plan",
                                 "reason": "plan deadlocked: no step has its dependencies met"})
    rest = [s for s in steps if s not in ready]
    return _dispatch(state, ready, rest, tx, norm, candidates, completed)


def _dispatch(state, ready, rest, tx, norm, candidates, completed):
    """Resolve + validate ready steps; stash the remainder generically."""
    from app.ai_assistant.mcp import adapter
    from app.ai_assistant import orchestration as orch

    # normalized date entities ride along as plain memory for the resolver
    tx = {**tx}
    for k in ("date_iso", "days", "time_window", "day_part", "time_range"):
        if norm.get(k) is not None and tx.get(k) in (None, "", 0):
            tx[k] = norm[k]
    batch, deferred = [], list(rest)
    pend = None
    for step in ready:
        tool = step["tool"]
        if tool not in adapter.known_tools():
            return _fail(state, {}, {"wanted": tool, "reason": "no matching capability"})
        resolved, error = orch.resolve_args(tool, step.get("args", {}), state, tx)
        if not error:
            resolved, error = adapter.validate(tool, resolved)
        if error:
            return _fail(state, resolved, {"wanted": tool, "reason": error})
        need, why = orch.needs_approval(tool, resolved)
        approved_ids = set(state.get("approved_step_ids") or [])
        if need and step.get("id") not in approved_ids and not step.get("approved"):
            pend = {"tool": tool, "args": resolved, "step_id": step.get("id", ""),
                    "reason": why, "remaining_plan": deferred + [s for s in ready if s is not step]}
            deferred = deferred + [s for s in ready if s is not step]
            continue
        pol = orch.policy_for(tool)
        if pol.get("parallel_safe", True):
            batch.append({**step, "args": resolved})
        else:
            # exclusive tool: runs alone; other ready steps wait
            if not batch:
                batch.append({**step, "args": resolved})
            else:
                deferred.append(step)
            deferred.extend([s for s in ready if s is not step and s not in batch
                             and s not in deferred])
            break
    if pend and not batch:
        trace = [*state.get("trace", []), f"router:approval:{pend['tool']}"]
        return {"selected_tool": "", "tool_args": {}, "plan_steps": deferred,
                "plan_batch": [], "missing_tool": {}, "pending_approval": pend,
                "chain_hint": "", "trace": trace}
    if not batch:
        # every ready step errored or pended; deferred holds the rest
        if pend:
            trace = [*state.get("trace", []), f"router:approval:{pend['tool']}"]
            return {"selected_tool": "", "tool_args": {}, "plan_steps": deferred,
                    "plan_batch": batch, "missing_tool": {}, "pending_approval": pend,
                    "chain_hint": "", "trace": trace}
        return _fail(state, {}, {"wanted": "plan", "reason": "no executable step"})
    first, rest_batch = batch[0], batch[1:]
    trace = [*state.get("trace", []),
             f"router:{first['tool']}" + (f"+{len(batch) - 1 + len(deferred)}" if len(batch) + len(deferred) > 1 else "")]
    out = {"selected_tool": first["tool"], "tool_args": first["args"],
           "plan_steps": deferred + rest_batch,
           "plan_batch": rest_batch,
           "missing_tool": {}, "plan_active": bool(deferred or rest_batch),
           "pending_confirmation": {"tool": first["tool"], "args": first["args"],
                                    "idempotency_key": uuid.uuid4().hex},
           "trace": trace}
    if pend:
        out["pending_approval"] = pend
    if state.get("pending_approval") and not pend:
        out["pending_approval"] = None
    return out


def _mark_approved(state: dict, step_id: str):
    ids = set(state.get("approved_step_ids") or [])
    if step_id:
        ids.add(step_id)
    state["approved_step_ids"] = sorted(ids)


def _fail(state, args, missing, label: str | None = None):
    trace = [*state.get("trace", []), label or f"router:invalid({missing.get('wanted', '?')})"]
    if not label and missing.get("reason") == "no capable tool":
        trace = [*state.get("trace", []), "router:unavailable"]
    return {"selected_tool": "", "tool_args": args, "plan_steps": [],
            "plan_batch": [], "missing_tool": missing,
            "chain_hint": "", "trace": trace}


# ---- compatibility shims (deprecated; kept so old imports keep working) ----

def _wire(args: dict, state: dict) -> dict:
    """Legacy ref wiring — delegates to the generic resolver."""
    from app.ai_assistant import orchestration as orch
    out = dict(args or {})
    for k, v in list(out.items()):
        if isinstance(v, str) and (v.startswith("$prev.") or v.startswith("$step_")):
            resolved, ok = orch._lookup_ref(v, state)
            if ok:
                out[k] = resolved
    return out


def route_after_router(state: dict) -> str:
    if state.get("pending_approval"):
        return "response"
    if state.get("selected_tool"):
        return "result"
    return "response"
