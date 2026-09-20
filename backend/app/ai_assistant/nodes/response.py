"""response node: LLM writes the reply from verified facts only. No hardcode."""
from __future__ import annotations

import json
import re
import time

_CLINICAL_OUT = re.compile(
    r"\byou have (a|an|the)\b.*\b(condition|disease|syndrome|disorder|infection|cancer)\b",
    re.IGNORECASE)

_BANNED = (
    "working to secure", "still working", "incomplete data",
    "contact citycare", "contact the hospital", "call the hospital",
    "log into", "patient portal", "front desk", "reviewing your questionnaire",
    "reviewing your records", "retrieved, i will share", "schedule is retrieved",
    "connect you with a human", "connect you to a human", "connect me to a human",
    "human assistant", "live agent", "team member", "will follow up",
    "follow up shortly", "reach out",
)

_DENIAL_PATTERNS = (
    "don't have access", "do not have access", "no access to",
    "cannot access", "can't access", "cant access", "couldn't access",
    "unable to book", "unable to schedule", "unable to check",
    # Only flagged when no tool ran (tool_ok False) — genuine empty-slot
    # results have tool_ok True and keep their honest wording.
    "no current availability", "no availability",
)

_SPECULATIVE = (
    "explore other", "try a different", "try another", "other providers",
    "other dates", "other doctors", "you could also", "i recommend",
    "why don't you", "why dont you",
)

_BOOKED_CLAIM = re.compile(
    r"\b(booked|booking confirmed|confirmed your appointment|scheduled|reserved)\b"
    r"|appointment\s+#?\d+\s+(is\s+)?(booked|confirmed)",
    re.IGNORECASE)


def violations(reply: str, tool_ok: bool, booking_proven: bool = False,
               dup_hits: int = 0, speculative: bool = False) -> list[str]:
    """Pure validator: banned stall/deflection phrasing + opener + false denials
    + false booking confirmations + text/card duplication + speculation."""
    low = (reply or "").lower()
    hits = [b for b in _BANNED if b in low]
    if low.startswith("you reported"):
        hits.append("opener:you reported")
    if not tool_ok and any(p in low for p in _DENIAL_PATTERNS):
        hits.append("false-denial")
    if _BOOKED_CLAIM.search(reply or "") and not booking_proven:
        hits.append("false-booking")
    if dup_hits >= 3:
        hits.append("text-duplicates-card")
    if speculative and any(p in low for p in _SPECULATIVE):
        hits.append("speculation")
    return hits


def _dup_count(reply: str, card: dict) -> int:
    """Count card facts (names, dates, times) repeated in the reply text."""
    if not card or not isinstance(card.get("items"), list):
        return 0
    low = (reply or "").lower()
    n = 0
    for it in card["items"]:
        if not isinstance(it, dict):
            continue
        for key in ("doctor_name", "name", "hospital_name", "title"):
            v = str(it.get(key, "")).strip()
            if len(v) > 3 and v.lower() in low:
                n += 1
        for key in ("starts_at", "ends_at"):
            v = str(it.get(key, ""))
            m = re.search(r"(\d{4}-\d{2}-\d{2})", v)
            if m and m.group(1) in (reply or ""):
                n += 1
            m = re.search(r"T(\d{2}:\d{2})", v)
            if m and (m.group(1) in low or _hm_alt(m.group(1)) in low):
                n += 1
    return n


def _hm_alt(hm: str) -> str:
    try:
        h, m = int(hm[:2]), hm[3:5]
        ap = "am" if h < 12 else "pm"
        h12 = h % 12 or 12
        return f"{h12}:{m} {ap}"
    except Exception:
        return hm


def _slot_label(starts_at: str) -> str:
    try:
        from datetime import datetime as _dt
        dt = _dt.fromisoformat(str(starts_at).replace("Z", "+00:00"))
        return dt.strftime("%a %b %d %I:%M %p").replace(" 0", " ")
    except Exception:
        return str(starts_at)


def _card(tool: str, data: dict, doctor_name: str = "") -> dict:
    """Build card payload from verified tool data. Every actionable item gets
    `actions: [{label, text}]` — tapping sends `text` as the next user message.
    Fully data-driven: labels/texts are composed from item fields only."""
    if not isinstance(data, dict):
        return {}
    if tool in ("search_doctors",) and isinstance(data.get("doctors"), list):
        items = []
        for d in data["doctors"][:6]:
            name = d.get("doctor_name", d.get("name", "this doctor"))
            hosp = d.get("hospital_name", "")
            where = f" at {hosp}" if hosp else ""
            items.append({**d, "actions": [
                {"label": "Check availability", "text": f"Check availability for {name}{where}"},
                {"label": "Book", "text": f"Book appointment with {name}{where}"},
            ]})
        return {"card": "doctors", "items": items}
    if tool in ("search_hospitals",) and isinstance(data.get("hospitals"), list):
        items = []
        for h in data["hospitals"][:6]:
            name = h.get("hospital_name", h.get("name", "this hospital"))
            items.append({**h, "actions": [
                {"label": "View doctors", "text": f"Show doctors at {name}"},
            ]})
        return {"card": "hospitals", "items": items}
    if tool in ("check_availability",) and isinstance(data.get("slots"), list):
        items = []
        for s in data["slots"][:8]:
            who = f" with {doctor_name}" if doctor_name else ""
            items.append({**s, "actions": [
                {"label": f"Book {_slot_label(s.get('starts_at', ''))}",
                 "text": f"Book {_slot_label(s.get('starts_at', ''))}{who}"},
            ]})
        return {"card": "slots", "items": items,
                "doctor_id": data.get("doctor_id")}
    if tool in ("create_appointment", "reschedule_appointment", "cancel_appointment",
                "get_appointment"):
        if data.get("appointment_id") or data.get("id"):
            aid = data.get("appointment_id") or data.get("id")
            return {"card": "appointment", "items": [{**data, "actions": [
                {"label": "Reschedule", "text": f"Reschedule appointment #{aid}"},
                {"label": "Cancel", "text": f"Cancel appointment #{aid}"},
            ]}]}
    if tool in ("get_questionnaire",) and data.get("id"):
        return {"card": "questionnaire", "items": [{**data, "actions": [
            {"label": "Answer", "text": f"Start questionnaire {data.get('title', '')}".strip()},
        ]}]}
    if tool in ("list_my_questionnaires",) and isinstance(data.get("questionnaires"), list):
        items = []
        for q in data["questionnaires"][:6]:
            items.append({**q, "actions": [
                {"label": "Fill", "text": f"Fill questionnaire {q.get('title', '')}".strip()},
            ]})
        return {"card": "questionnaires", "items": items}
    if tool in ("list_my_appointments",) and isinstance(data.get("appointments"), list):
        items = []
        for a in data["appointments"][:6]:
            items.append({**a, "actions": [
                {"label": "Details", "text": f"Show details of appointment #{a.get('id')}"},
            ]})
        return {"card": "appointments", "items": items}
    if tool in ("get_reviews",) and isinstance(data.get("reviews"), list):
        return {"card": "reviews", "items": data["reviews"][:5],
                "avg": data.get("avg"), "count": data.get("count")}
    return {}


def _options(state: dict) -> list[dict]:
    """Tappable input options when the assistant needs a reply. Built only from
    state (clarification fields, prior tool data, transactional memory)."""
    safety = state.get("safety") or {}
    if safety.get("verdict") == "escalate":
        if (state.get("transfer") or {}).get("escalated"):
            return []  # already logged this turn — no duplicate records
        return [
            {"label": "Yes, log it", "text": "Yes, log this for the care team"},
            {"label": "Not now", "text": "No thanks"},
        ]
    fields = state.get("pending_clarification_fields") or []
    if not fields:
        return []
    tx = (state.get("context_refs") or {}).get("transactional") or {}
    if isinstance(tx, str):
        try:
            tx = json.loads(tx)
        except Exception:
            tx = {}
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
    if "appointment" in fields or "new_time" in fields:
        for a in _appts():
            opts.append({"label": f"Appt #{a.get('id')} {_slot_label(a.get('starts_at', ''))}",
                         "text": f"Appointment #{a.get('id')}"})
    if "date_hint" in fields or "new_time" in fields:
        if tx.get("date_iso"):
            for part in ("Morning", "Afternoon", "Evening"):
                opts.append({"label": part, "text": part})
        else:
            for day in ("Today", "Tomorrow", "This week"):
                opts.append({"label": day, "text": day})
    if "appointment_or_form" in fields:
        for a in _appts():
            opts.append({"label": f"Appt #{a.get('id')}", "text": f"Appointment #{a.get('id')}"})
    seen, unique = set(), []
    for o in opts:
        if o["text"] not in seen:
            seen.add(o["text"])
            unique.append(o)
    return unique[:4]


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
    doctor_name = ""
    if card_tool == "check_availability":
        try:
            from app.models import Doctor
            did = (data or {}).get("doctor_id") or 0
            d = db.query(Doctor).filter(Doctor.id == int(did)).first()
            doctor_name = d.name if d else ""
        except Exception:
            doctor_name = ""
    card = _card(card_tool, data, doctor_name)
    if not card:
        # Fall back to the last successful plan step (partial multi-step results).
        for s in reversed(state.get("step_outputs") or []):
            card = _card(s.get("tool", ""), s.get("data", {}), doctor_name)
            if card:
                break
    hints = {
        "safety": safety, "intent": state.get("intent"),
        "classification": state.get("classification"),
        "scope": state.get("scope_hint", ""),
        "clarify_fields": state.get("pending_clarification_fields", []),
        "tool": tool, "tool_status": state.get("tool_status", ""),
        "tool_data": json.dumps(data)[:3000],
        "prior_step_data": json.dumps(state.get("step_outputs") or [])[:3000],
        "missing_tool": state.get("missing_tool", {}),
        "transfer": state.get("transfer", {}),
        "summary": state.get("conversation_summary", ""),
        "card_will_render": bool(card),
        "card_kind": (card or {}).get("card", ""),
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
    if _CLINICAL_OUT.search(reply):
        fix = await llm_mod.generate(
            [{"role": "user", "content": "Rewrite without any clinical conclusion. "
              "Echo only patient-reported words as theirs. Text: " + reply[:2000]}],
            system=ADMIN_SYSTEM)
        reply = fix.content.strip()
        res = fix
    tool_ok = bool((state.get("tool_result") or {}).get("ok"))
    if not tool:
        # Clarification-pending turns have no tool yet — a "don't have
        # access" reply there is a false denial (must ask the missing
        # question instead), so mark not-ok to trigger the rewrite.
        tool_ok = not bool(state.get("missing_tool") or state.get("scope_hint")
                           or state.get("pending_clarification_fields"))
    booking_proven = (
        tool == "create_appointment" and bool((state.get("tool_result") or {}).get("ok"))
        and bool((data or {}).get("verified") or (data or {}).get("appointment_id")))
    has_data = bool(data) and tool_ok
    dup = _dup_count(reply, card) if card else 0
    if violations(reply, tool_ok, booking_proven, dup, speculative=not has_data):
        fix = await llm_mod.generate(
            [{"role": "user", "content": (
                "Rewrite this reply plainly: open with the answer, no 'You reported' opener, "
                "no claims about background work or record reviews, no phone/portal referrals, "
                "no capability denials when tools exist, and never claim an appointment is "
                "booked/confirmed unless the tool result proves it. There is NO live human "
                "agent: never promise a connection, handoff, callback, or follow-up — "
                "escalation means a tracked request logged for the care team, cited by its "
                "reference number when present. If a card renders the "
                "details, keep the reply to ONE short line and do not repeat names, times, "
                "or lists. When no tool data exists, state the fact plainly and offer a "
                "human — never suggest other providers, dates, or workarounds. Text: "
                + reply[:2000])}],
            system=ADMIN_SYSTEM)
        if fix.content.strip():
            reply = fix.content.strip()
            res = fix
    db.add(AIMessage(conversation_id=state.get("conversation_id"), role="assistant",
                     content=reply[:4000], latency_ms=int((time.time() - t0) * 1000)))
    db.commit()
    trace = [*state.get("trace", []), f"response:{res.powered_by}"]
    options = _options(state)
    payload = {}
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
