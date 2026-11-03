"""response node: purely LLM-driven reply + LLM-driven chat UI.

The LLM writes the reply from verified facts and designs the card UI
(layout, wording, buttons) in the user's language. Code only enforces
structural invariants: no unverified booking claims (LLM self-check) and no
hallucinated UI references (validate_ui: every id/date cited by a button must
exist in verified tool output). The deterministic build_card remains as the
fallback when the LLM UI is unavailable or fails validation.
"""
from __future__ import annotations

import json
import time


def _slot_label(starts_at: str) -> str:
    try:
        from datetime import datetime as _dt
        dt = _dt.fromisoformat(str(starts_at).replace("Z", "+00:00"))
        return dt.strftime("%a %b %d %I:%M %p").replace(" 0", " ")
    except Exception:
        return str(starts_at)


def _has_list_payload(data: dict) -> bool:
    """True when data holds at least one non-empty list of dicts (cardable)."""
    if not isinstance(data, dict):
        return False
    return any(isinstance(v, list) and v and isinstance(v[0], dict)
               for v in data.values())


def _card(tool: str, data: dict, doctor_name: str = "") -> dict:
    """Generic card builder: delegates to orchestration.build_card() which
    renders ANY tool's list payload with registry-derived follow-up actions.
    No per-tool branches — new tools render with zero changes here."""
    from app.ai_assistant import orchestration as orch

    if not isinstance(data, dict):
        return {}
    card = orch.build_card(tool, data)
    # Slot labels stay human-readable using the contextual doctor name.
    if card.get("card") == "slots" and doctor_name:
        for it in card.get("items", []):
            for a in it.get("actions", []):
                if a.get("text") and doctor_name not in a["text"]:
                    a["text"] = f"{a['text']} with {doctor_name}"
    # Legacy kind aliases keep the existing frontend renderer working.
    aliases = {"doctor": "doctors", "hospital": "hospitals", "slot": "slots",
               "appointment": "appointment", "questionnaire": "questionnaires",
               "review": "reviews"}
    kind = str(card.get("card", ""))
    if kind in aliases:
        card["card"] = aliases[kind]
    return card


async def _llm_options(state: dict, card: dict) -> list[dict]:
    """LLM-generated tappable options from live state (no fixed day lists).

    Falls back to data-driven candidates (verified doctors/appointments)
    when the LLM is unavailable — never to hardcoded Today/Tomorrow words.
    """
    from app.ai_assistant.services import llm as llm_mod

    safety = state.get("safety") or {}
    if safety.get("verdict") == "escalate":
        if (state.get("transfer") or {}).get("escalated"):
            return []
        # Escalation confirmation is a structural flow, worded by the LLM
        # response itself; keep minimal affirmative actions data-driven.
        return [
            {"label": "Yes", "text": "Yes"},
            {"label": "Not now", "text": "Not now"},
        ]
    fields = state.get("pending_clarification_fields") or []
    if not fields:
        return []
    # Data-driven candidates from verified outputs (global, any language).
    cands: list[dict] = []

    def _doctors():
        for s in reversed(state.get("step_outputs") or []):
            docs = (s.get("data") or {}).get("doctors")
            if isinstance(docs, list) and docs:
                return docs[:3]
        return []

    def _appts():
        for s in reversed(state.get("step_outputs") or []):
            appts = (s.get("data") or {}).get("appointments")
            if isinstance(appts, list) and appts:
                return appts[:3]
        return []

    cand_text = json.dumps({"fields": fields,
                            "doctors": _doctors(),
                            "appointments": _appts()})[:1500]
    try:
        res = await llm_mod.generate(
            [{"role": "user", "content": f"Fields missing: {fields}. Candidates: {cand_text}. "
              "Reply JSON only: {\"options\": [{\"label\": \"\", \"text\": \"\"}]}. "
              "Max 4 options, each text must be sendable as the next user message "
              "in the user's language. Use candidate names verbatim."}],
            system="You generate tappable reply options. JSON only.")
        try:
            data = json.loads(res.content)
        except Exception:
            s, e = res.content.find("{"), res.content.rfind("}")
            data = json.loads(res.content[s:e + 1]) if s >= 0 and e > s else {}
        opts = data.get("options", [])
        if isinstance(opts, list):
            out = [{"label": str(o.get("label", ""))[:60],
                    "text": str(o.get("text", ""))[:200]}
                   for o in opts if isinstance(o, dict) and o.get("text")]
            # De-dup preserve order, cap 4.
            seen, uniq = set(), []
            for o in out:
                if o["text"] not in seen:
                    seen.add(o["text"])
                    uniq.append(o)
            return uniq[:4]
    except Exception:
        pass
    # Fallback: raw candidates as options (no hardcoded words).
    out: list[dict] = []
    for d in _doctors():
        name = d.get("doctor_name", d.get("name", ""))
        hosp = d.get("hospital_name", "")
        if name:
            out.append({"label": f"{name}" + (f" · {hosp}" if hosp else ""),
                        "text": f"{name}" + (f" at {hosp}" if hosp else "")})
    for a in _appts():
        out.append({"label": f"Appointment #{a.get('id')}",
                    "text": f"Appointment #{a.get('id')}"})
    seen, uniq = set(), []
    for o in out:
        if o["text"] not in seen:
            seen.add(o["text"])
            uniq.append(o)
    return uniq[:4]


# ---- Back-compat shims for tests / callers (LLM-first semantics) ----

def violations(reply: str, tool_ok: bool, booking_proven: bool = False,
               dup_hits: int = 0, speculative: bool = False,
               data: dict | None = None) -> list[str]:
    """Structural guard only: flag unproven record claims.

    Language-agnostic and data-aware: a concrete reference (#<digits>) is
    fine when that id exists anywhere in the verified tool output (e.g. an
    escalation reference number); it is flagged only when the cited number
    matches nothing the tools returned — no word lists in any language.
    The async path (_needs_rewrite) adds LLM wording review on top.
    """
    import re as _re
    if booking_proven:
        return []
    refs = set(_re.findall(r"#\s*(\d+)", reply or ""))
    if not refs:
        return []
    known: set[str] = set()

    def _collect(v):
        if isinstance(v, dict):
            for x in v.values():
                _collect(x)
        elif isinstance(v, list):
            for x in v:
                _collect(x)
        elif isinstance(v, int):
            known.add(str(v))
        elif isinstance(v, str) and v.isdigit():
            known.add(v.lstrip("0") or "0")

    _collect(data or {})
    if refs <= {n.lstrip("0") or "0" for n in known} | known:
        return []
    return ["false-booking"]


def _dup_count(reply: str, card: dict) -> int:
    """Kept for compatibility: duplication is now handled by the LLM prompt
    (card_will_render -> one short line). Always returns 0 (no penalty)."""
    return 0


def _options(state: dict) -> list[dict]:
    """Sync compat: data-driven candidates only (no hardcoded day lists).

    Async path uses _llm_options. This returns verified doctors/appointments
    as options, or [] — never Today/Tomorrow/This week constants.
    """
    safety = state.get("safety") or {}
    if safety.get("verdict") == "escalate":
        if (state.get("transfer") or {}).get("escalated"):
            return []
        return [
            {"label": "Yes, log it", "text": "Yes, log this for the care team"},
            {"label": "Not now", "text": "No thanks"},
        ]
    fields = state.get("pending_clarification_fields") or []
    if not fields:
        return []
    opts: list[dict] = []

    def _doctors():
        for s in reversed(state.get("step_outputs") or []):
            docs = (s.get("data") or {}).get("doctors")
            if isinstance(docs, list) and docs:
                return docs[:3]
        return []

    def _appts():
        for s in reversed(state.get("step_outputs") or []):
            appts = (s.get("data") or {}).get("appointments")
            if isinstance(appts, list) and appts:
                return appts[:3]
        return []

    if "specialty_or_doctor" in fields:
        for d in _doctors():
            name = d.get("doctor_name", d.get("name", ""))
            hosp = d.get("hospital_name", "")
            if not name:
                continue
            where = f" at {hosp}" if hosp else ""
            opts.append({"label": f"{name}{where}", "text": f"{name}{where}"})
    if "appointment" in fields or "new_time" in fields or "appointment_or_form" in fields:
        for a in _appts():
            opts.append({"label": f"Appt #{a.get('id')}",
                         "text": f"Appointment #{a.get('id')}"})
    seen, unique = set(), []
    for o in opts:
        if o["text"] not in seen:
            seen.add(o["text"])
            unique.append(o)
    return unique[:4]


async def _needs_rewrite(reply: str, tool_ok: bool, booking_proven: bool,
                         has_data: bool) -> bool:
    """LLM self-check: does the reply claim background work, live-agent
    promises, or unproven bookings? Pure LLM, no word lists."""
    from app.ai_assistant.services import llm as llm_mod

    if booking_proven:
        return False
    try:
        res = await llm_mod.generate(
            [{"role": "user", "content": (
                "Reply text: " + reply[:1500] +
                f"\nFlags: tool_ok={tool_ok} booking_proven={booking_proven} has_data={has_data}. "
                "Does this text (in ANY language) claim (a) an appointment is booked/confirmed "
                "without proof, or (b) a live human agent/handoff/callback/phone/portal action, "
                "or (c) background work ('securing/ reviewing records') not in tool data? "
                'Reply JSON only: {"rewrite": true|false}.')}],
            system="You audit assistant replies. JSON only.")
        try:
            data = json.loads(res.content)
        except Exception:
            s, e = res.content.find("{"), res.content.rfind("}")
            data = json.loads(res.content[s:e + 1]) if s >= 0 and e > s else {}
        return bool(data.get("rewrite", False))
    except Exception:
        # Fail-open to old structural shim (never block on auditor failure).
        return bool(violations(reply, tool_ok, booking_proven))


async def run(state: dict) -> dict:
    rt = state.get("_runtime", {}) or {}
    db = rt.get("db")
    corr = rt.get("corr", "")
    from app.ai_assistant.prompts.system import ADMIN_SYSTEM, RESPONSE_SYSTEM
    from app.ai_assistant.services import llm as llm_mod
    from app.models import AIMessage

    safety = state.get("safety") or {}
    tool = state.get("selected_tool", "")
    result = state.get("tool_result") or {}
    data = result.get("data", {}) if isinstance(result.get("data"), dict) else {}
    # Build the card BEFORE the reply so the LLM knows details render in cards.
    card_tool = tool or state.get("last_tool", "")
    # Display name for slot labels: resolved from verified output by field,
    # never by tool name. Falls back to a DB lookup on doctor_id if present.
    doctor_name = str((data or {}).get("doctor_name", "") or "")
    if not doctor_name and (data or {}).get("doctor_id"):
        try:
            from app.models import Doctor
            d = db.query(Doctor).filter(
                Doctor.id == int((data or {}).get("doctor_id") or 0)).first()
            doctor_name = d.name if d else ""
        except Exception:
            doctor_name = ""
    from app.ai_assistant import orchestration as _orch_ui
    # LLM-designed UI first (full-LLM chat templates), deterministic
    # build_card as the fallback. UI data/doctor may come from a previous
    # plan step when the last tool returned no list payload.
    ui_source = data if _has_list_payload(data) else {}
    ui_tool = card_tool
    if not ui_source:
        for s in reversed(state.get("step_outputs") or []):
            sdata = (s or {}).get("data", {})
            if _has_list_payload(sdata):
                ui_source, ui_tool = sdata, (s or {}).get("tool", "")
                break
    _cls = state.get("classification") or {}
    _lang = str(_cls.get("language", "")) if isinstance(_cls, dict) else ""
    ui: dict = {}
    if ui_source:
        try:
            raw_ui = await _orch_ui.build_ui_llm(
                ui_tool, ui_source, language=_lang, doctor_name=doctor_name)
            ui = _orch_ui.validate_ui(raw_ui, ui_source)
        except Exception:
            ui = {}
    trace_ui = f"ui:{'llm' if ui else 'fallback'}"
    card = _card(card_tool, data, doctor_name)
    if not card:
        # Fall back to the last successful plan step (partial multi-step results).
        for s in reversed(state.get("step_outputs") or []):
            card = _card(s.get("tool", ""), s.get("data", {}), doctor_name)
            if card:
                break
    cls = state.get("classification") or {}
    hints = {
        "safety": safety, "intent": state.get("intent"),
        "classification": cls,
        "language": cls.get("language", ""),
        "scope": state.get("scope_hint", ""),
        "clarify_fields": state.get("pending_clarification_fields", []),
        "tool": tool, "tool_status": state.get("tool_status", ""),
        "tool_data": json.dumps(data)[:3000],
        "prior_step_data": json.dumps(state.get("step_outputs") or [])[:3000],
        "missing_tool": state.get("missing_tool", {}),
        "transfer": state.get("transfer", {}),
        "summary": state.get("conversation_summary", ""),
        "card_will_render": bool(ui or card),
        "card_kind": (ui or {}).get("kind", "") or (card or {}).get("card", ""),
    }
    messages = [{"role": "system", "content": ADMIN_SYSTEM}]
    if state.get("conversation_summary"):
        messages.append({"role": "system",
                         "content": f"Conversation summary: {state['conversation_summary'][:1000]}"})
    for m in (state.get("messages", []) or [])[-5:]:
        messages.append({"role": m.get("role", "user"), "content": m.get("content", "")[:1500]})
    t0 = time.time()
    try:
        res = await llm_mod.generate(
            messages[1:],
            system=ADMIN_SYSTEM + "\n" + RESPONSE_SYSTEM.format(hints=json.dumps(hints)[:3500]))
    except Exception:
        raise
    reply = res.content.strip()
    tool_ok = bool((state.get("tool_result") or {}).get("ok"))
    if not tool:
        tool_ok = not bool(state.get("missing_tool") or state.get("scope_hint")
                           or state.get("pending_clarification_fields"))
    from app.ai_assistant import orchestration as _orch
    booking_proven = (
        bool((state.get("tool_result") or {}).get("ok"))
        and _orch.is_proven_result(tool or state.get("last_tool", ""), data))
    has_data = bool(data) and tool_ok
    if await _needs_rewrite(reply, tool_ok, booking_proven, has_data):
        fix = await llm_mod.generate(
            [{"role": "user", "content": (
                "Rewrite this reply in the user's language: open with the answer, "
                "ground every fact in verified tool data, never claim an appointment is "
                "booked/confirmed unless the tool result proves it. There is NO live human "
                "agent: never promise a connection, handoff, callback, or follow-up — "
                "escalation means a tracked request logged for the care team, cited by its "
                "reference number when present. If a card renders the "
                "details, keep the reply to ONE short line. When no tool data exists, "
                "state the fact plainly and offer a tracked request — never invent "
                "providers, dates, or workarounds. Text: "
                + reply[:2000])}],
            system=ADMIN_SYSTEM)
        if fix.content.strip():
            reply = fix.content.strip()
            res = fix
    db.add(AIMessage(conversation_id=state.get("conversation_id"), role="assistant",
                     content=reply[:4000], latency_ms=int((time.time() - t0) * 1000)))
    db.commit()
    trace = [*state.get("trace", []), f"response:{res.powered_by}", trace_ui]
    try:
        options = await _llm_options(state, card)
    except Exception:
        options = _options(state)
    payload = {}
    if ui:
        payload["ui"] = ui
    if card:
        payload["card"] = card["card"]
        payload.update({k: v for k, v in card.items() if k != "card"})
    if options:
        payload["options"] = options
    try:
        row = db.query(AIMessage).filter(
            AIMessage.conversation_id == state.get("conversation_id"),
            AIMessage.role == "assistant").order_by(AIMessage.id.desc()).first()
        if row is not None and payload:
            row.data_json = json.dumps(payload)[:8000]
            db.commit()
    except Exception:
        db.rollback()
    return {"reply": reply, "powered_by": res.powered_by,
            "data": payload, "trace": trace}
