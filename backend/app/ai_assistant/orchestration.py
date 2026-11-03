"""Generic tool orchestration: planning catalog, plan validation,
argument resolution, policy checks, dependency scheduling, UI cards.

No tool names appear here. All tool knowledge comes from
``mcp.registry`` (schemas, policies, descriptions) at runtime, so adding a
new MCP tool never requires touching this module, the router, the executor
or the response builder.
"""
from __future__ import annotations

import json
import re


def _cfg(name: str, default):
    try:
        from app.core.config import settings
        return getattr(settings, name, default)
    except Exception:
        return default


# ---------------------------------------------------------------- catalog

def build_catalog() -> tuple[list[str], str]:
    """Return (tool_names, planner catalog text) from the live registry."""
    from app.ai_assistant.mcp import registry as reg

    return reg.tool_names(), reg.describe_catalog()


# ------------------------------------------------------- plan validation

def validate_plan(plan) -> tuple[list[dict], dict]:
    """Validate an LLM-produced plan generically.

    Accepted shape: [{id?, tool, args?, depends_on?}] plus legacy
    {tool, args} single-step. Returns (steps, error). error is {} when ok,
    else {wanted, reason, alternatives}.
    """
    from app.ai_assistant.mcp import registry as reg

    if not isinstance(plan, list):
        return [], {"wanted": "plan", "reason": "plan must be a list of steps"}
    known = set(reg.tool_names())
    steps: list[dict] = []
    seen_ids: set[str] = set()
    for i, raw in enumerate(plan):
        if not isinstance(raw, dict):
            return [], {"wanted": f"step_{i}", "reason": "each plan step must be an object"}
        tool = str(raw.get("tool", "")).strip()
        if not tool:
            return [], {"wanted": f"step_{i}", "reason": "step is missing 'tool'"}
        if tool not in known:
            return [], {"wanted": tool, "reason": "no matching capability",
                         "alternatives": sorted(known)[:5]}
        sid = str(raw.get("id") or f"step_{i}")
        if sid in seen_ids:
            return [], {"wanted": sid, "reason": "duplicate step id"}
        seen_ids.add(sid)
        args = raw.get("args", {})
        if not isinstance(args, dict):
            return [], {"wanted": tool, "reason": f"args for '{tool}' must be an object"}
        deps = raw.get("depends_on", [])
        if deps is None:
            deps = []
        if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps):
            return [], {"wanted": tool, "reason": f"depends_on for '{tool}' must be a list of step ids"}
        steps.append({"id": sid, "tool": tool, "args": dict(args), "depends_on": list(deps)})
    # dependency references must exist; no self-loops / simple cycle check
    by_id = {s["id"]: s for s in steps}
    for s in steps:
        for d in s["depends_on"]:
            if d not in by_id:
                return [], {"wanted": s["tool"], "reason": f"unknown depends_on '{d}'"}
            if d == s["id"]:
                return [], {"wanted": s["tool"], "reason": "step cannot depend on itself"}
    # cycle detection (DFS)
    visiting, done = set(), set()

    def _visit(sid: str) -> bool:
        if sid in done:
            return False
        if sid in visiting:
            return True
        visiting.add(sid)
        for d in by_id[sid]["depends_on"]:
            if _visit(d):
                return True
        visiting.discard(sid)
        done.add(sid)
        return False

    for s in steps:
        if _visit(s["id"]):
            return [], {"wanted": s["tool"], "reason": "circular depends_on in plan"}
    return steps, {}


def ready_steps(plan_steps: list[dict], completed_ids: set[str]) -> list[dict]:
    """Steps whose dependencies are all completed (parallel-safe batch)."""
    return [s for s in (plan_steps or [])
            if all(d in completed_ids for d in s.get("depends_on", []))]


# ------------------------------------------------- argument resolution

_REF_RE = re.compile(r"^\$(prev|step_[A-Za-z0-9_\-]+)\.(.+)$")


def _lookup_ref(ref: str, state: dict):
    m = _REF_RE.match(str(ref or ""))
    if not m:
        return ref, False
    scope, field = m.group(1), m.group(2)
    if scope == "prev":
        data = (state.get("tool_result") or {}).get("data", {})
        if isinstance(data, dict) and field in data:
            return data[field], True
        return ref, False
    for s in state.get("step_outputs") or []:
        if s.get("step_id") == scope or s.get("tool") == scope:
            data = s.get("data", {})
            if isinstance(data, dict) and field in data:
                return data[field], True
    # fall back: search every completed step output for the field
    for s in state.get("step_outputs") or []:
        data = s.get("data", {})
        if isinstance(data, dict) and field in data:
            return data[field], True
    return ref, False


def collect_candidates(state: dict) -> list[dict]:
    """Harvest {ids + names} seen in history tool data (tool-agnostic).

    Collects any dict inside list-valued tool output that carries an id-like
    key plus a name-like key — works for doctors, hospitals, appointments or
    any future tool without naming it.
    """
    keep = int(_cfg("AI_CANDIDATE_KEEP", 12))
    out, seen = [], set()
    for m in state.get("messages", []) or []:
        if not isinstance(m, dict):
            continue
        content = m.get("content", "") or ""
        try:
            data = content if isinstance(content, dict) else json.loads(
                content[content.find("{"):] if content.find("{") >= 0 else content)
        except Exception:
            continue
        if not isinstance(data, dict):
            continue
        for key, items in data.items():
            if not isinstance(items, list):
                continue
            # A bare `id` inside e.g. a "doctors" list means that list's
            # entity (doctors -> doctor_id). Derived generically from the key.
            alias = key[:-1] + "_id" if key.endswith("s") and len(key) > 1 else ""
            for it in items:
                if not isinstance(it, dict):
                    continue
                ids = {k: it.get(k) for k in
                       ("doctor_id", "hospital_id", "appointment_id", "id",
                        "patient_id", "questionnaire_id", "response_id")
                       if it.get(k) not in (None, "", 0)}
                if "id" in ids and alias and alias not in ids:
                    ids[alias] = ids["id"]
                if not ids:
                    continue
                name = (it.get("doctor_name") or it.get("hospital_name")
                        or it.get("full_name") or it.get("name")
                        or it.get("title", ""))
                ck = (tuple(sorted(ids.items())), str(name))
                if ck in seen:
                    continue
                seen.add(ck)
                out.append({"ids": ids, "name": str(name),
                            "hospital_name": str(it.get("hospital_name", ""))})
    return out[-keep:]


def _coerce_value(v, kind: str):
    if kind == "int" and v not in (None, ""):
        try:
            return int(v), ""
        except (TypeError, ValueError):
            return v, f"must be an integer"
    return v, ""


def resolve_args(tool: str, raw_args: dict | None, state: dict,
                 entities: dict | None = None) -> tuple[dict, str]:
    """Resolve final args for ANY tool generically (no tool branches).

    Precedence: explicit LLM args > $prev/$step refs > transactional entities
    > history candidates > runtime identity > verified slot outputs.
    Then coerce types + validate required via the registry schema.
    """
    from app.ai_assistant.mcp import registry as reg

    spec = reg.get_schema(tool)
    required = spec.get("required", [])
    int_args = set(spec.get("int_args", []))
    args = dict(raw_args or {})
    tx = dict(entities or {})
    ttx = (state.get("context_refs") or {}).get("transactional") or {}
    if isinstance(ttx, dict):
        for k, v in ttx.items():
            tx.setdefault(k, v)

    # 1) resolve $prev./$step. references against completed outputs
    for k, v in list(args.items()):
        if isinstance(v, str) and (v.startswith("$prev.") or v.startswith("$step_")):
            resolved, ok = _lookup_ref(v, state)
            if ok:
                args[k] = resolved

    # 2) entity merge: any missing REQUIRED arg filled from memory keys.
    #    Conventional aliases (date<-date_iso, day_part<-time_window, ...) let
    #    the LLM speak naturally while schemas stay strict — no tool names.
    aliases = {"date": ("date_iso",), "days": ("days",),
               "day_part": ("day_part", "time_window"),
               "time_range": ("time_range",),
               "q": ("q", "doctor_name", "hospital_name", "specialty")}
    candidates = collect_candidates(state)
    # Required args first, then conventional temporal/search hints so tools
    # with optional date filters still benefit from normalized entities.
    wanted = list(required) + [k for k in aliases if k not in required]
    for k in wanted:
        if args.get(k) not in (None, ""):
            continue
        for cand_key in (k, *aliases.get(k, ())):
            if tx.get(cand_key) not in (None, "", 0):
                args[k] = tx[cand_key]
                break
        if args.get(k) not in (None, ""):
            continue
        if k.endswith("_id"):
            for c in candidates:
                if k in c.get("ids", {}):
                    args[k] = c["ids"][k]
                    break

    # 3) runtime identity (never spoofable by the LLM)
    rt = state.get("_runtime", {}) or {}
    user = rt.get("user")
    if user is not None and getattr(user, "patient_id", None):
        args.setdefault("patient_id", user.patient_id)
    if not args.get("conversation_id") and state.get("conversation_id"):
        if "conversation_id" in required:
            args["conversation_id"] = state["conversation_id"]

    # 4) verified slot outputs can satisfy any slot-shaped requirement
    if any(k in required for k in ("starts_at", "ends_at")) and \
            not (args.get("starts_at") and args.get("ends_at")):
        slot = _find_verified_slot(state, args.get("doctor_id") or tx.get("doctor_id"),
                                   tx.get("date_iso", ""))
        if slot:
            for sk in ("starts_at", "ends_at", "calendar_id", "hospital_id"):
                if slot.get(sk) is not None:
                    args.setdefault(sk, slot[sk])

    # 5) type coercion + required validation from the schema
    coerced = dict(args)
    for k in int_args:
        if coerced.get(k) in (None, ""):
            continue
        coerced[k], err = _coerce_value(coerced[k], "int")
        if err:
            return args, f"Argument {k} {err}."
    missing = [k for k in required if coerced.get(k) in (None, "")]
    if missing:
        return coerced, f"Missing required arguments: {', '.join(missing)}."
    return coerced, ""


def _find_verified_slot(state: dict, doctor_id, date_iso: str) -> dict:
    """Return first verified slot matching doctor/date from this turn or DB."""
    from app.ai_assistant.mcp import registry as reg

    pools: list[dict] = []
    for s in (state.get("step_outputs") or []):
        for it in ((s.get("data") or {}).get("slots") or []):
            if isinstance(it, dict):
                pools.append(it)
    try:
        rt, db, cid = state.get("_runtime", {}) or {}, None, state.get("conversation_id")
        db = rt.get("db")
        if db is not None and cid:
            from app.models import AIMessage as _M
            rows = (db.query(_M).filter(_M.conversation_id == int(cid), _M.role == "tool")
                    .order_by(_M.id.desc()).limit(int(_cfg("AI_TOOL_MSG_KEEP", 3))).all())
            for r in rows:
                try:
                    payload = json.loads(r.content or "{}")
                except Exception:
                    continue
                data = payload.get("data", payload) if isinstance(payload, dict) else {}
                if isinstance(data, dict):
                    pools.extend([it for it in data.get("slots") or [] if isinstance(it, dict)])
    except Exception:
        pass
    try:
        did = int(doctor_id or 0)
    except (TypeError, ValueError):
        did = 0
    # honor an LLM time_range when present in entities
    tx = (state.get("context_refs") or {}).get("transactional") or {}
    tr = (tx if isinstance(tx, dict) else {}).get("time_range") or {}
    lo_hi = None
    try:
        if isinstance(tr, dict) and tr.get("start_hr") is not None:
            lo_hi = (int(tr["start_hr"]), int(tr["end_hr"]))
    except (TypeError, ValueError):
        lo_hi = None
    cands = [s for s in pools
             if (not did or int(s.get("doctor_id") or 0) == did)
             and (not date_iso or str(s.get("starts_at", "")).startswith(str(date_iso)))]
    if not cands:
        return {}
    if lo_hi:
        lo, hi = lo_hi
        for s in cands:
            try:
                from datetime import datetime as _dt
                if lo <= _dt.fromisoformat(str(s["starts_at"]).replace("Z", "+00:00")).hour < hi:
                    return s
            except Exception:
                continue
    # fall back to the registry's generic picker (no invented times)
    try:
        return reg.pick_verified_slot(cands, doctor_id=did, date_iso=str(date_iso or ""))
    except Exception:
        return cands[0]


# ---------------------------------------------------------------- policies

def policy_for(tool: str) -> dict:
    from app.ai_assistant.mcp import registry as reg
    return reg.get_policy(tool)


def needs_approval(tool: str, args: dict) -> tuple[bool, str]:
    """Deterministic approval gate. Never LLM-decided."""
    pol = policy_for(tool)
    if pol.get("approval_required"):
        return True, f"Tool '{tool}' requires human approval per policy."
    return False, ""


def timeout_for(tool: str) -> float:
    try:
        return float(policy_for(tool).get("timeout_s", 25) or 25)
    except (TypeError, ValueError):
        return 25.0


# ------------------------------------------------------- result helpers

def has_actionable_data(data: dict) -> bool:
    """Generic: any non-empty list in tool output means follow-up may help."""
    if not isinstance(data, dict):
        return False
    return any(isinstance(v, list) and len(v) > 0 for v in data.values())


def is_proven_result(tool: str, data: dict) -> bool:
    """Generic proof check, no tool names: an explicit verified flag, an
    appointment reference, or an id paired with a lifecycle marker (search
    listings carry bare ids with no status, so they never count)."""
    if not isinstance(data, dict):
        return False
    if data.get("verified") is True:
        return True
    if data.get("appointment_id"):
        return True
    return bool(data.get("id") and (data.get("status") or data.get("verified") is not None))


# ----------------------------------------------------------- UI cards

def build_card(tool: str, data: dict, page: int | None = None) -> dict:
    """Deterministic fallback card builder for ANY tool: finds the first list
    payload in the result, paginates it, and attaches follow-up actions
    derived from the registry (which tools can consume this item's fields).
    Preferred path is build_ui_llm + validate_ui; this runs when the LLM UI
    is unavailable or fails validation."""
    if not isinstance(data, dict):
        return {}
    try:
        per_page = int(_cfg("AI_CARD_PAGE", 10))
    except (TypeError, ValueError):
        per_page = 10
    for key, items in data.items():
        if not isinstance(items, list) or not items or not isinstance(items[0], dict):
            continue
        shown = items[:per_page]
        out = []
        for it in shown:
            acts = actions_for_item(it, exclude_tool=tool)
            if it.get("starts_at"):
                # time-selectable item: direct booking action from its own
                # fields (no tool knowledge; executor resolves the slot).
                label = _slot_label(str(it.get("starts_at", "")))
                acts = [{"label": f"Book {label}", "text": f"Book {label}"},
                        *acts][:3]
            else:
                acts = acts[:3]
            out.append({**it, "actions": acts})
        card = {"card": key, "items": out}
        for extra in ("doctor_id", "avg", "count"):
            if data.get(extra) is not None:
                card[extra] = data[extra]
        return card
    # single-object results (appointment/questionnaire/detail dicts)
    if data.get("appointment_id") or (data.get("id") and data.get("status")):
        aid = data.get("appointment_id") or data.get("id")
        acts = actions_for_item({"appointment_id": aid}, exclude_tool=tool)
        return {"card": "appointment", "items": [{**data, "actions": acts[:3]}]}
    if data.get("id") and (data.get("title") or data.get("schema")):
        acts = actions_for_item({"questionnaire_id": data.get("id")}, exclude_tool=tool)
        return {"card": "questionnaire", "items": [{**data, "actions": acts[:3]}]}
    return {}


def actions_for_item(item: dict, exclude_tool: str = "") -> list[dict]:
    """Which registered tools can consume this item's fields? Generic."""
    from app.ai_assistant.mcp import registry as reg

    if not isinstance(item, dict):
        return []
    have = {k for k, v in item.items() if v not in (None, "", 0, [])}
    # id-alias: a bare `id` satisfies any *_id requirement when only one
    # id-like field exists (covers search results across tools).
    id_keys = [k for k in have if k == "id" or k.endswith("_id")]
    suggestions: list[dict] = []
    for t in reg.CAPABILITIES:
        name = t["name"]
        if name == exclude_tool:
            continue
        req = set(reg.get_schema(name).get("required", []))
        if not req:
            continue
        if req <= have:
            fillable = True
        elif len(req - have) == 1 and id_keys:
            missing = (req - have).pop()
            fillable = missing.endswith("_id")
        else:
            fillable = False
        if not fillable:
            continue
        # human-readable follow-up text built from the item's own fields
        # (_action_label drops candidates whose template fields are missing)
        label = _action_label(name, item)
        if label:
            suggestions.append({"label": label[0], "text": label[1]})
        if len(suggestions) >= 6:
            break
    return suggestions


def collect_known_values(data) -> tuple[set[str], set[str]]:
    """All reference numbers and ISO dates in verified output.

    Used to prove an LLM-generated button cites only real values —
    language-agnostic (digits and ISO format look the same everywhere).
    """
    import re as _re

    numbers, dates = set(), set()

    def _walk(v):
        if isinstance(v, dict):
            for x in v.values():
                _walk(x)
        elif isinstance(v, list):
            for x in v:
                _walk(x)
        elif isinstance(v, bool):
            return
        elif isinstance(v, int):
            numbers.add(str(v))
        elif isinstance(v, float):
            numbers.add(str(int(v)))
        elif isinstance(v, str):
            for d in _re.findall(r"\d{4}-\d{2}-\d{2}", v):
                dates.add(d)
            for n in _re.findall(r"#\s*(\d+)", v):
                numbers.add(n.lstrip("0") or "0")
            if v.isdigit():
                numbers.add(v.lstrip("0") or "0")

    _walk(data)
    return numbers, dates


def validate_ui(ui: dict, verified: dict) -> dict:
    """Validate LLM-generated chat UI. Drops hallucinated actions, keeps real.

    Rules (structural only): correct shape; non-empty label/text within
    length caps; every #<digits> reference, bare 3+-digit number and ISO date
    in an action's text must exist in the verified tool output. Invalid
    actions are dropped; items survive without actions (display-only).
    Returns a sanitized ui dict, or {} when nothing usable remains.
    """
    import re as _re

    if not isinstance(ui, dict):
        return {}
    items = ui.get("items")
    if not isinstance(items, list) or not items:
        return {}
    try:
        per_page = int(_cfg("AI_CARD_PAGE", 10))
    except (TypeError, ValueError):
        per_page = 10
    known_numbers, known_dates = collect_known_values(verified)
    clean_items = []
    for it in items[:per_page]:
        if not isinstance(it, dict):
            continue
        clean_actions = []
        for a in it.get("actions", []) or []:
            if not isinstance(a, dict):
                continue
            label, text = str(a.get("label", ""))[:60].strip(), str(a.get("text", ""))[:200].strip()
            if not label or not text:
                continue
            refs = {n.lstrip("0") or "0" for n in _re.findall(r"#\s*(\d+)", text)}
            bare = {n.lstrip("0") or "0" for n in _re.findall(r"(?<!\d)(\d{3,})(?!\d)", text)}
            dates = set(_re.findall(r"\d{4}-\d{2}-\d{2}", text))
            if not refs <= known_numbers:
                continue
            if not bare <= known_numbers:
                continue
            if not dates <= known_dates:
                continue
            clean_actions.append({"label": label, "text": text})
        entry = {k: v for k, v in it.items() if k != "actions"}
        entry["actions"] = clean_actions[:3]
        clean_items.append(entry)
    if not clean_items:
        return {}
    out = {"kind": str(ui.get("kind", "results"))[:40] or "results",
           "items": clean_items}
    if ui.get("title"):
        out["title"] = str(ui["title"])[:120]
    return out


async def build_ui_llm(tool: str, data: dict, *, language: str = "",
                       doctor_name: str = "") -> dict:
    """Ask the LLM to design the chat card UI from verified output.

    Returns the raw parsed dict (unvalidated — callers must pass it through
    validate_ui). Returns {} when the LLM is unavailable or unparsable.
    TOOL_ACTIONS metadata is only prompt inspiration, never runtime logic.
    """
    import json as _j

    from app.ai_assistant.prompts.system import UI_SCHEMA_SYSTEM

    if not isinstance(data, dict) or not data:
        return {}
    try:
        from app.ai_assistant.services import llm as llm_mod
        per_page = int(_cfg("AI_CARD_PAGE", 10))
    except (TypeError, ValueError):
        per_page = 10
    compact: dict = {}
    for key, val in data.items():
        if isinstance(val, list):
            compact[key] = val[:per_page]
        else:
            compact[key] = val
    prompt_data = {"tool": tool, "language": language or "auto",
                   "doctor_name": doctor_name, "data": compact}
    try:
        system = UI_SCHEMA_SYSTEM.replace("__PAGE__", str(per_page)) \
            .replace("__DATA__", _j.dumps(prompt_data)[:3000])
        res = await llm_mod.generate(
            [{"role": "user", "content": "Design the card UI. JSON only."}],
            system=system)
        text = (res.content or "").strip()
        if text.startswith("```"):
            text = text.strip("`")
            nl = text.find("\n")
            text = text[nl + 1:] if nl >= 0 else ""
            if text.rstrip().endswith("```"):
                text = text.rstrip()[:-3]
        try:
            parsed = _j.loads(text)
        except Exception:
            s, e = text.find("{"), text.rfind("}")
            parsed = _j.loads(text[s:e + 1]) if s >= 0 and e > s else {}
        return parsed if isinstance(parsed, dict) else {}
    except Exception:
        return {}


def _slot_label(starts_at: str) -> str:
    try:
        from datetime import datetime as _dt
        return _dt.fromisoformat(str(starts_at).replace("Z", "+00:00")) \
            .strftime("%a %b %d %I:%M %p").replace(" 0", " ")
    except Exception:
        return str(starts_at)


def _action_label(tool: str, item: dict) -> tuple[str, str] | None:
    """Render a follow-up button from the tool's registered metadata template.

    No tool names here: text comes from ``registry.TOOL_ACTIONS`` with the
    item's own fields as placeholders. Tools without a template get a
    generic fallback derived from the tool name.
    """
    from app.ai_assistant.mcp import registry as reg

    if not isinstance(item, dict):
        return None
    name = (item.get("doctor_name") or item.get("name") or "").strip()
    hosp = (item.get("hospital_name") or "").strip()
    fields = {"name": name, "where": f" at {hosp}" if hosp else "",
              "ref": str(item.get("appointment_id") or item.get("id") or ""),
              "title": str(item.get("title") or item.get("questionnaire_id") or "").strip()}
    tmpl = reg.get_action_template(tool)
    if tmpl:
        template = str(tmpl.get("text", ""))
        # Skip when the item lacks a field the template needs (generic:
        # decided by the template's own placeholders, not by tool name).
        for key in ("name", "ref", "title"):
            if "{%s}" % key in template and not fields[key]:
                return None
        try:
            text = template.format(**fields).strip()
            label = str(tmpl.get("label", "")).strip()
        except (KeyError, IndexError, ValueError):
            return None
        if not label or not text:
            return None
        return (label, text)
    pretty = tool.replace("_", " ").strip().capitalize()
    return (pretty, f"{pretty} about {name or fields['ref'] or 'this'}".strip())
