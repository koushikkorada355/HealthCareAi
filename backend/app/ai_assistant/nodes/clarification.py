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
    import re as _re
    _last_user = ""
    for _m in reversed(state.get("messages", []) or []):
        if isinstance(_m, dict) and _m.get("role") == "user":
            _last_user = str(_m.get("content", ""))
            break
    out_extra: dict = {}
    missing: list[str] = []
    if intent == "book":
        tx_doc = tx.get("doctor_id") or tx.get("doctor_name") or tx.get("specialty")
        if not (cls.get("specialty") or tx_doc):
            # Fresh-turn doctor-name mentions ("Check availability for
            # Dr. Tom Becker") carry no specialty and no tx yet — resolve the
            # name deterministically so the turn reaches check_availability.
            _hit = _mention_doctor(state, _last_user)
            if _hit:
                _tx2 = dict(tx)
                _tx2.setdefault("doctor_name", _hit["doctor_name"])
                if _hit.get("doctor_id"):
                    _tx2.setdefault("doctor_id", _hit["doctor_id"])
                refs = dict(ctx)
                refs["transactional"] = _tx2
                out_extra["context_refs"] = refs
                tx = _tx2
                tx_doc = True
            else:
                missing.append("specialty_or_doctor")
        # Slot/availability follow-ups ("give slots first", "show availability")
        # with a known doctor must reach check_availability (defaults days=7).
        # Blocking them on date_hint produced the "don't have access" denial.
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
    return {"pending_clarification_fields": missing, "trace": trace, **out_extra}


def _mention_doctor(state: dict, text: str) -> dict:
    """Match a named active doctor in free text (fresh turns, no tx yet).

    Returns {doctor_id, doctor_name} or {}. Surname match requires 4+ chars
    with word boundaries to avoid false hits on common words.
    """
    import re as _re

    try:
        rt = state.get("_runtime", {}) or {}
        db = rt.get("db")
        if db is None or not text:
            return {}
        from app.models import Doctor as _D

        rows = db.query(_D).filter(_D.status == "active").all()
        low = f" {text.lower()} "
        best: dict = {}
        best_len = 0
        for d in rows:
            core = (d.name or "").lower().replace("dr.", " ").strip()
            core = _re.sub(r"\s+", " ", core)
            if not core:
                continue
            hit_len = 0
            if _re.search(rf"\b{_re.escape(core)}\b", low):
                hit_len = len(core)
            else:
                surname = core.split()[-1]
                if len(surname) >= 4 and _re.search(rf"\b{_re.escape(surname)}\b", low):
                    hit_len = len(surname)
            if hit_len > best_len:
                best_len = hit_len
                best = {"doctor_id": d.id, "doctor_name": d.name}
        return best
    except Exception:
        return {}


def route_after_clarification(state: dict) -> str:
    if state.get("pending_clarification_fields"):
        return "response"
    if state.get("intent") in ("greeting",):
        return "response"
    return "tool_router"
