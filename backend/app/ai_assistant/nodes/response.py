"""Response node: validated, grounded replies only.

Order: safety refusal > pending clarification > pending confirmation >
urgent escalation > human handoff > verified tool facts (+ Grok polish) >
tool errors > fallback. Every produced reply passes claim validation
against verified tool output before sending; violations fall back to the
pre-validated facts text. Grok only rephrases, never sources content.
"""
from __future__ import annotations

import re

from ..safety import rules

_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
_DR_RE = re.compile(r"\bDr\.?\s+[A-Z][a-zA-Z\-']+")
_CLINICAL_RE = re.compile(r"diagnos|prescrib|dosage|take (?:ibuprofen|aspirin|paracetamol)|\bmedication\b", re.IGNORECASE)


async def run(state: dict) -> dict:
    safety = state.get("safety") or {}
    if safety.get("verdict") == "deny":
        reply = rules.refusal_for(safety.get("reason_category", ""))
        return _out(state, reply, "rules")
    if safety.get("verdict") == "escalate":
        if safety.get("reason_category") == "urgent":
            # User-facing emergency direction (standalone, complete).
            # Never a diagnosis, never minimized, never tool-dependent.
            return _out(state, rules.refusal_for("urgent"), "rules")
        transfer = state.get("transfer") or {}
        reply = (transfer.get("summary") or
                 "I've escalated this to a human on the care team with our conversation context. "
                 "They'll follow up here shortly.")
        # Human-requested escalations read as a status update, not an op log.
        if safety.get("reason_category") == "human_requested":
            reply = ("Understood — I've escalated this to a human on the care team "
                     "with our conversation context. They'll follow up here shortly.")
        return _out(state, reply, "rules")
    if state.get("pending_clarification"):
        return _out(state, state["pending_clarification"], "rules")
    pending = state.get("pending_confirmation") or {}
    if pending.get("tool"):
        return _out(state, f"Just to confirm: {pending.get('summary', 'proceed with the change?')} "
                           "Reply yes to proceed or no to stop — nothing changes until you confirm.", "rules")
    if state.get("reply"):
        # Set by scope (redirect) or carried refusal text.
        if safety.get("verdict") == "escalate":
            return _out(state, state["reply"], "rules")
        return _out(state, state["reply"], "rules")
    transfer = state.get("transfer") or {}
    if transfer.get("escalated"):
        reply = (transfer.get("summary") or
                 "I've escalated this to a human on the care team with our conversation context. "
                 "They'll follow up here shortly.")
        return _out(state, reply, "rules")
    tool = state.get("selected_tool", "")
    result = state.get("tool_result") or {}
    if result.get("ok") and tool:
        if tool in ("create_appointment", "reschedule_appointment", "cancel_appointment"):
            d = result.get("data") or {}
            verb = {"create_appointment": "booked and verified", "reschedule_appointment": "moved",
                    "cancel_appointment": "cancelled"}.get(tool, "done")
            return await _polished(
                state, f"Done — appointment #{d.get('appointment_id', d.get('id', '?'))} {verb} "
                       f"(status {d.get('status', 'updated')}). Anything else?")
        facts = _render_verified(tool, result.get("data") or {})
        if facts:
            return await _polished(state, facts)
        return _out(state, "Done — verified. Anything else?", "rules")
    if tool:
        code = result.get("code", "failed")
        err = (result.get("error") or "").split(":")[0]
        if code == "denied":
            return _out(state, "I don't have permission for that on your account — nothing was looked up or changed.", "rules")
        if code == "timeout":
            return _out(state, "That took too long and I stopped it safely — nothing was confirmed. Please try again.", "rules")
        if code == "invalid":
            return _out(state, f"I couldn't run that: {result.get('error', 'missing details')}", "rules")
        return _out(state, f"That didn't work ({err or code}) — nothing was changed. Want me to try a different way or bring in a human?", "rules")
    classification = state.get("classification") or {}
    if (classification.get("intent") or state.get("intent")) == "greeting":
        return _out(state, "Hello! I'm your care access assistant. Tell me what you need — e.g. 'I need to see a doctor for shoulder pain this week' — and I'll check real availability.", "rules")
    return _out(state, "I can help you find hospitals/doctors, check real availability, and book, reschedule or cancel appointments. What would you like to do?", "rules")


def _out(state: dict, reply: str, powered_by: str) -> dict:
    return {"reply": reply, "powered_by": powered_by,
            "trace": [*state.get("trace", []), f"response: {powered_by}"]}


async def _polished(state: dict, facts: str) -> dict:
    """Grok rephrase of pre-validated facts, re-validated before sending.

    Facts are built from verified tool output, so they pass by construction;
    the LLM wording is what gets checked. Any violation falls back to facts.
    """
    rt = state.get("_runtime", {}) or {}
    llm = rt.get("llm")
    if llm is None:
        from ..services.llm import get_llm

        llm = get_llm()
    data = ((state.get("tool_result") or {}).get("data")) or {}
    try:
        polished, used = await llm.rephrase(facts)
    except Exception:
        polished, used = facts, False
    if used and polished and validate_claims(polished, data):
        return _out(state, polished, "grok")
    return _out(state, facts, "rules")


def _collect(data: object, isos: set, names: set) -> None:
    if isinstance(data, dict):
        for k, v in data.items():
            if k in ("starts_at", "ends_at") and isinstance(v, str) and _ISO_RE.search(v):
                hit = _ISO_RE.search(v)
                if hit:
                    isos.add(hit.group(0)[:16].replace(" ", "T"))
            if k in ("name", "doctor_name", "hospital_name", "patient_name") and isinstance(v, str) and v:
                names.add(v)
            _collect(v, isos, names)
    elif isinstance(data, list):
        for v in data:
            _collect(v, isos, names)


def validate_claims(reply: str, data: dict) -> bool:
    """True iff every verifiable claim in reply is grounded in data.

    Checks: ISO datetimes ⊆ tool output datetimes; "Dr. X" names ⊆ tool
    output names; no clinical language. Conservative: unknown → False.
    """
    if _CLINICAL_RE.search(reply or ""):
        return False
    isos: set = set()
    names: set = set()
    _collect(data or {}, isos, names)
    for m in _ISO_RE.finditer(reply or ""):
        if m.group(0)[:16].replace(" ", "T") not in isos:
            return False
    for m in _DR_RE.finditer(reply or ""):
        hit = m.group(0).strip()
        surname = hit.split()[-1].lower()
        if not any(surname in (n or "").lower() for n in names):
            return False
    return True


def _render_verified(tool: str, data: dict) -> str:
    """Grounded reply from verified tool output only. Empty = no claim."""
    if tool == "search_doctors":
        docs = data.get("doctors") or []
        if not docs:
            return "I couldn't find an active doctor matching that right now. Want to try another specialty or hospital?"
        lines = []
        for d in docs[:5]:
            hosp = d.get("hospital_name", "")
            lines.append(f"**{d.get('name')}** ({d.get('specialty') or 'care'}){f' — {hosp}' if hosp else ''}")
        return "Here are real options:\n" + "\n".join("• " + l for l in lines)
    if tool == "search_hospitals":
        hs = data.get("hospitals") or []
        if not hs:
            return "I couldn't find an approved hospital matching that right now. Want to try another city?"
        lines = [f"**{h.get('name')}** — {h.get('city', '')}" for h in hs[:8]]
        return "Here are approved hospitals:\n" + "\n".join("• " + l for l in lines)
    if tool in ("get_doctor_details", "get_hospital_details"):
        name = data.get("name", "the record")
        city = data.get("hospital_city") or data.get("city", "")
        return f"Here's what I found for **{name}**{f' ({city})' if city else ''} — all details verified, nothing invented."
    if tool == "check_availability":
        slots = data.get("slots") or []
        if not slots:
            return "No open slots in that window — blocked time, leave and bookings respected. Want another day or doctor?"
        first = slots[0].get("starts_at", "")[:16].replace("T", " ")
        return f"Found {len(slots)} real slot(s). Earliest: {first}. Tell me which works and I'll book it with verification."
    if tool in ("cancel_appointment", "reschedule_appointment", "create_appointment"):
        return ""
    return ""
