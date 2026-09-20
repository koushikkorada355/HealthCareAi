"""tool_router node: LLM picks one MCP tool (validated, never invoked here)."""
from __future__ import annotations

import json
import uuid


async def run(state: dict) -> dict:
    from app.ai_assistant.mcp import adapter
    from app.ai_assistant.mcp import registry as reg
    from app.ai_assistant.prompts.system import ROUTER_SYSTEM
    from app.ai_assistant.services import llm as llm_mod
    from app.ai_assistant.utils.dates import normalize as normalize_dates

    tools = adapter.known_tools()
    lines = []
    for t in reg.CAPABILITIES:
        req = ", ".join(adapter.REQUIRED_ARGS.get(t["name"], [])) or "none"
        lines.append(f"- {t['name']}: {t['description']} [required: {req}]")
    catalog = "\n".join(lines)
    tx = (state.get("context_refs") or {}).get("transactional") or {}
    if isinstance(tx, str):
        try:
            tx = json.loads(tx)
        except Exception:
            tx = {}
    candidates = _candidates(state)
    norm = _norm(state, tx)

    pending = list(state.get("plan_steps") or [])
    if pending:
        # Continue a stored multi-step plan — no LLM call needed.
        step = pending[0]
        rest = pending[1:]
        tool, args = str(step.get("tool", "")), step.get("args", {})
        if tool == state.get("last_tool"):
            trace = [*state.get("trace", []), f"router:repeat({tool})"]
            return {"selected_tool": "", "tool_args": {}, "plan_steps": [],
                    "missing_tool": {"wanted": tool, "reason": "already called this turn"},
                    "chain_hint": "", "trace": trace}
        args = _wire(_backfill(tool, args, state, norm, candidates, tx), state)
        if tool not in tools:
            trace = [*state.get("trace", []), "router:plan-bad"]
            return {"selected_tool": "", "tool_args": {}, "plan_steps": [],
                    "missing_tool": {"wanted": tool, "reason": "planned tool unknown"},
                    "trace": trace}
        coerced, error = adapter.validate(tool, args)
        if error:
            trace = [*state.get("trace", []), f"router:plan-invalid({tool})"]
            return {"selected_tool": "", "tool_args": args, "plan_steps": [],
                    "missing_tool": {"wanted": tool, "reason": error}, "trace": trace}
        trace = [*state.get("trace", []), f"router:plan:{tool}"]
        return {"selected_tool": tool, "tool_args": coerced, "plan_steps": rest,
                "missing_tool": {}, "plan_active": True,
                "pending_confirmation": {"tool": tool, "args": coerced,
                                         "idempotency_key": uuid.uuid4().hex},
                "trace": trace}

    history = state.get("history_text", "")[-2000:]
    summary = state.get("conversation_summary", "")[:800]
    ctx = json.dumps(state.get("context_refs", {}))[:1500]
    cls_d = state.get("classification", {}) or {}
    cls = json.dumps(cls_d)[:800]
    chain = state.get("chain_hint", "")
    prompt = (
        f"Intent: {state.get('intent')}\nClassification: {cls}\nSummary: {summary}\n"
        f"Context: {ctx}\nKnown entities: {json.dumps(tx)[:600]}\n"
        f"Normalized date: {json.dumps(norm)}\n"
        f"Candidate IDs (name/hospital -> ids, use these, do not re-search): "
        f"{json.dumps(candidates)[:1200]}\n"
        f"History:\n{history}\nChain hint: {chain}\n"
        "Plan this request globally (direct, multi-step, or unavailable). JSON only.")
    try:
        res = await llm_mod.generate([{"role": "user", "content": prompt}],
                                     system=ROUTER_SYSTEM.replace("__CATALOG__", catalog))
        try:
            data = json.loads(res.content)
        except Exception:
            s, e = res.content.find("{"), res.content.rfind("}")
            data = json.loads(res.content[s:e + 1]) if s >= 0 and e > s else {}
    except Exception:
        raise
    # Back-compat: older single-tool shape {tool, args} still accepted.
    plan = data.get("plan")
    if not isinstance(plan, list):
        t1, a1 = str(data.get("tool", "none")), data.get("args", {})
        plan = [{"tool": t1, "args": a1 if isinstance(a1, dict) else {}}] \
            if t1 not in ("", "none") else []
    if not plan:
        trace = [*state.get("trace", []), "router:unavailable"]
        return {"selected_tool": "", "tool_args": {}, "plan_steps": [],
                "missing_tool": {"wanted": str(data.get("unavailable", "unknown")),
                                 "reason": "no capable tool",
                                 "alternatives": data.get("alternatives", [])},
                "trace": trace}
    first, rest = plan[0], plan[1:]
    tool = str(first.get("tool", ""))
    args = first.get("args", {}) if isinstance(first.get("args"), dict) else {}
    if tool == state.get("last_tool"):
        # Same tool twice in a row never helps — answer with what we have.
        trace = [*state.get("trace", []), f"router:repeat({tool})"]
        return {"selected_tool": "", "tool_args": {}, "plan_steps": [],
                "missing_tool": {"wanted": tool, "reason": "already called this turn"},
                "chain_hint": "", "trace": trace}
    args = _backfill(tool, args, state, norm, candidates, tx)
    if tool not in tools:
        trace = [*state.get("trace", []), f"router:missing_tool({tool})"]
        return {"selected_tool": "", "tool_args": {}, "plan_steps": [],
                "missing_tool": {"wanted": tool, "reason": "no matching capability"},
                "trace": trace}
    coerced, error = adapter.validate(tool, args)
    if error:
        trace = [*state.get("trace", []), f"router:invalid({tool})"]
        return {"selected_tool": "", "tool_args": args, "plan_steps": [],
                "missing_tool": {"wanted": tool, "reason": error}, "trace": trace}
    idem = uuid.uuid4().hex
    trace = [*state.get("trace", []),
             f"router:{tool}" + (f"+{len(rest)}" if rest else "")]
    return {"selected_tool": tool, "tool_args": coerced,
            "plan_steps": [s for s in rest if isinstance(s, dict)],
            "missing_tool": {}, "plan_active": bool(rest),
            "pending_confirmation": {"tool": tool, "args": coerced,
                                     "idempotency_key": idem},
            "trace": trace}


def _norm(state: dict, tx: dict) -> dict:
    from app.ai_assistant.utils.dates import normalize as normalize_dates

    last_text = ""
    for m in reversed(state.get("messages", [])):
        if isinstance(m, dict) and m.get("role") == "user":
            last_text = m.get("content", "")
            break
    cls_d = state.get("classification", {}) or {}
    return normalize_dates(last_text + " " + str(cls_d.get("dates", "")))


def _wire(args: dict, state: dict) -> dict:
    """Resolve $prev.<field> refs against the last tool result (plan wiring)."""
    prev = (state.get("tool_result") or {}).get("data", {})
    if not isinstance(prev, dict):
        return args
    wired = {}
    for k, v in (args or {}).items():
        if isinstance(v, str) and v.startswith("$prev."):
            wired[k] = prev.get(v[len("$prev."):], v)
        else:
            wired[k] = v
    return wired


def _candidates(state: dict) -> list[dict]:
    """Name/hospital -> IDs seen in history tool data (so the LLM reuses them)."""
    import json as _j

    out: list[dict] = []
    seen: set = set()
    for m in state.get("messages", []) or []:
        if not isinstance(m, dict):
            continue
        content = m.get("content", "") or ""
        if isinstance(content, dict):
            data = content
            items_src = True
        else:
            s = content.find("{")
            try:
                data = _j.loads(content[s:] if s >= 0 else content)
            except Exception:
                continue
        if not isinstance(data, dict):
            continue
        for key in ("doctors", "hospitals", "appointments"):
            items = data.get(key)
            if not isinstance(items, list):
                continue
            for it in items:
                if not isinstance(it, dict):
                    continue
                did = it.get("doctor_id", it.get("id") if key == "doctors" else 0) or 0
                hid = it.get("hospital_id", 0) or 0
                if not did and not hid:
                    continue
                ck = (did, hid, it.get("name", ""))
                if ck in seen:
                    continue
                seen.add(ck)
                out.append({"doctor_id": did,
                            "doctor_name": it.get("doctor_name", it.get("name", "")),
                            "hospital_id": hid,
                            "hospital_name": it.get("hospital_name", it.get("name", ""))})
    return out[-12:]


def _as_int(v):
    try:
        return int(v)
    except (TypeError, ValueError):
        return 0


def _backfill(tool: str, args: dict, state: dict, norm: dict,
              candidates: list[dict], tx: dict) -> dict:
    """Fill missing args from normalized dates + known entities (no LLM)."""
    args = dict(args or {})
    if tool == "check_availability":
        if not _as_int(args.get("doctor_id")):
            did = tx.get("doctor_id") or 0
            if not did and len(candidates) == 1:
                did = candidates[0]["doctor_id"]
            if not did:
                # Fall back to doctors returned by earlier plan steps this turn.
                for s in reversed(state.get("step_outputs") or []):
                    docs = (s.get("data") or {}).get("doctors") or []
                    if docs and isinstance(docs[0], dict) and docs[0].get("id"):
                        did = docs[0]["id"]
                        break
            if not did:
                lname = str(tx.get("doctor_name", "")).lower()
                for c in candidates:
                    if lname and lname in c["doctor_name"].lower():
                        if not did:
                            did = c["doctor_id"]
                        elif did != c["doctor_id"]:
                            did = 0
                            break
            if did:
                args["doctor_id"] = did
        if not args.get("date") and norm.get("date_iso"):
            args["date"] = norm["date_iso"]
        if not args.get("day_part"):
            tw = str(tx.get("time_window", "")).lower()
            if tw in ("morning", "afternoon", "evening"):
                args["day_part"] = tw
            elif norm.get("day_part"):
                args["day_part"] = norm["day_part"]
    elif tool in ("search_doctors", "get_reviews"):
        if not args.get("specialty") and tx.get("specialty"):
            args["specialty"] = tx["specialty"]
        if tool == "get_reviews" and not args.get("doctor_id") and tx.get("doctor_id"):
            args["doctor_id"] = tx["doctor_id"]
    elif tool == "create_appointment":
        rt = state.get("_runtime", {}) or {}
        user = rt.get("user")
        if not _as_int(args.get("patient_id")) and user is not None and getattr(user, "patient_id", None):
            args["patient_id"] = user.patient_id
        if not _as_int(args.get("hospital_id")) and tx.get("hospital_id"):
            args["hospital_id"] = tx["hospital_id"]
        if not _as_int(args.get("doctor_id")):
            did = tx.get("doctor_id") or 0
            if not did and len(candidates) == 1:
                did = candidates[0]["doctor_id"]
            if did:
                args["doctor_id"] = did
        if not (args.get("starts_at") and args.get("ends_at")):
            slot = _resolve_slot(state, norm, args.get("doctor_id") or tx.get("doctor_id"))
            if slot:
                args["starts_at"] = slot["starts_at"]
                args["ends_at"] = slot["ends_at"]
                args["calendar_id"] = slot.get("calendar_id")
                args.setdefault("hospital_id", slot.get("hospital_id", args.get("hospital_id")))
        else:
            # Unparsable datetimes from the planner are unusable — resolve instead.
            try:
                from datetime import datetime as _dt
                _dt.fromisoformat(str(args["starts_at"]).replace("Z", "+00:00"))
                _dt.fromisoformat(str(args["ends_at"]).replace("Z", "+00:00"))
            except (ValueError, TypeError):
                slot = _resolve_slot(state, norm, args.get("doctor_id") or tx.get("doctor_id"))
                if slot:
                    args["starts_at"] = slot["starts_at"]
                    args["ends_at"] = slot["ends_at"]
                    args["calendar_id"] = slot.get("calendar_id")
    return args


def _slot_lists(state: dict) -> list[dict]:
    """Collect verified slots from this turn + recent tool messages (DB)."""
    out: list[dict] = []
    for s in (state.get("step_outputs") or []):
        for it in ((s.get("data") or {}).get("slots") or []):
            if isinstance(it, dict):
                out.append(it)
    try:
        rt = state.get("_runtime", {}) or {}
        db = rt.get("db")
        cid = state.get("conversation_id")
        if db is not None and cid:
            import json as _j
            from app.models import AIMessage as _M
            rows = (db.query(_M).filter(_M.conversation_id == int(cid), _M.role == "tool")
                    .order_by(_M.id.desc()).limit(3).all())
            for r in rows:
                try:
                    payload = _j.loads(r.content or "{}")
                except Exception:
                    continue
                data = payload.get("data", payload) if isinstance(payload, dict) else {}
                if isinstance(data, dict):
                    for it in data.get("slots") or []:
                        if isinstance(it, dict):
                            out.append(it)
    except Exception:
        pass
    return out


def _resolve_slot(state: dict, norm: dict, doctor_id) -> dict:
    """Match a verified slot by doctor + normalized date (+ time window)."""
    try:
        did = int(doctor_id or 0)
    except (TypeError, ValueError):
        did = 0
    date_iso = (norm or {}).get("date_iso", "")
    part = (norm or {}).get("day_part", "")
    cands = []
    for s in _slot_lists(state):
        try:
            if did and int(s.get("doctor_id") or 0) != did:
                continue
        except (TypeError, ValueError):
            continue
        if date_iso and not str(s.get("starts_at", "")).startswith(date_iso):
            continue
        cands.append(s)
    if not cands:
        return {}
    if part in ("morning", "afternoon", "evening"):
        lo, hi = {"morning": (5, 12), "afternoon": (12, 17), "evening": (17, 22)}[part]
        timed = []
        for s in cands:
            try:
                from datetime import datetime as _dt
                hr = _dt.fromisoformat(str(s["starts_at"]).replace("Z", "+00:00")).hour
            except Exception:
                continue
            if lo <= hr < hi:
                timed.append(s)
        if timed:
            return timed[0]
    return cands[0]


def route_after_router(state: dict) -> str:
    if state.get("selected_tool"):
        return "result"
    return "response"
