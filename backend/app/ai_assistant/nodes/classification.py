"""Classification node: structured understanding via LLM + fallback."""
from __future__ import annotations

import re

# Short follow-ups referencing prior turns ("that", weekday, session words).
_FOLLOWUP_RE = re.compile(
    r"\b(that|it|this|them|those|same|other|another|friday|monday|tuesday|wednesday|thursday|saturday|sunday|tomorrow|today|morning|afternoon|evening|weekend|change|move it|make that)\b",
    re.IGNORECASE,
)
_CARRY_INTENTS = {"book", "find_doctor", "find_hospital", "profile", "availability", "reschedule", "cancel"}


async def run(state: dict) -> dict:
    rt = state.get("_runtime", {}) or {}
    llm = rt.get("llm")
    messages = state.get("messages", []) or []
    text = messages[-1].get("content", "") if messages else rt.get("text", "")
    history = state.get("history_text", "")

    if llm is None:
        from ..services.llm import get_llm

        llm = get_llm()
    cls = await llm.classify(text, history)
    out = {
        "category": cls.category,
        "intent": cls.intent,
        "entities": dict(cls.entities or {}),
        "confidence": cls.confidence,
        "needs_action_write": cls.needs_action_write,
    }
    # Follow-up resolution: a short message that only makes sense against the
    # prior turn (weekday/session change, "that") inherits the prior intent +
    # entities instead of dying as unknown/unrelated. History alone is not
    # trusted for facts — only for resolving references.
    refs = dict(state.get("context_refs") or {})
    if (cls.intent == "unknown" and refs.get("intent") in _CARRY_INTENTS
            and len(text) < 80 and _FOLLOWUP_RE.search(text)):
        out["intent"] = refs["intent"]
        out["category"] = "administrative"
        merged = dict(refs)
        for k, v in (cls.entities or {}).items():
            if v not in (None, ""):
                merged[k] = v
        out["entities"] = {k: merged[k] for k in ("specialty", "city", "doctor_id", "hospital_id", "appointment_id", "date_pref") if merged.get(k) not in (None, "")}
        out["confidence"] = max(cls.confidence, 0.6)
    return {
        "intent": out["intent"],
        "classification": out,
        "trace": [*state.get("trace", []),
                  f"classify: {out['category']}/{out['intent']} ({llm.name})"],
    }
