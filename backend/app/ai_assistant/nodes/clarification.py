"""clarification node: compute missing tool fields (hint only, LLM phrases)."""
from __future__ import annotations

_NEEDS = {
    "book": ["specialty_or_doctor", "date_hint"],
    "reschedule": ["appointment", "new_time"],
    "cancel": ["appointment"],
    "lookup": [],
    "questionnaire": [],
    "admin_q": [],
    "greeting": [],
}


async def run(state: dict) -> dict:
    intent = state.get("intent", "ambiguous")
    cls = state.get("classification") or {}
    ctx = state.get("context_refs") or {}
    tx = ctx.get("transactional") or {}
    if isinstance(tx, str):
        try:
            import json as _j
            tx = _j.loads(tx)
        except Exception:
            tx = {}
    missing: list[str] = []
    if intent == "book":
        tx_doc = tx.get("doctor_id") or tx.get("doctor_name") or tx.get("specialty")
        if not (cls.get("specialty") or tx_doc):
            missing.append("specialty_or_doctor")
        # Slot/availability follow-ups ("give slots first", "show availability")
        # with a known doctor must reach check_availability (defaults days=7).
        # Blocking them on date_hint produced the "don't have access" denial.
        import re as _re
        _last_user = ""
        for _m in reversed(state.get("messages", []) or []):
            if isinstance(_m, dict) and _m.get("role") == "user":
                _last_user = str(_m.get("content", ""))
                break
        _wants_slots = bool(_re.search(
            r"\bslots?\b|\bavailab|\bopen\b|\bfirst\b|\bshow\b|\bcheck\b",
            _last_user, _re.IGNORECASE))
        if not (cls.get("dates") or tx.get("date_iso")) and not (_wants_slots and tx_doc):
            missing.append("date_hint")
    else:
        for f in _NEEDS.get(intent, []):
            missing.append(f)
    trace = [*state.get("trace", []),
             f"clarification:{','.join(missing) if missing else 'complete'}"]
    return {"pending_clarification_fields": missing, "trace": trace}


def route_after_clarification(state: dict) -> str:
    if state.get("pending_clarification_fields"):
        return "response"
    if state.get("intent") in ("greeting",):
        return "response"
    return "tool_router"
