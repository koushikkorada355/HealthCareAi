"""safety node: LLM verdict primary; deterministic urgent list only upgrades.

Sets state['safety'] = {verdict: allow|deny|escalate, reason}. Never tools,
never the final reply here.
"""
from __future__ import annotations

import json
import re

_URGENT = re.compile(
    r"chest\s*(pain|pressure|tight)|trouble\s*breath|can'?t\s*breath|uncontrolled\s*bleed|"
    r"stroke|slurred\s*speech|suicid|kill\s*myself|overdose|severe\s*allergic|anaphylax",
    re.IGNORECASE)
_HUMAN = re.compile(r"\b(human|agent|person|someone real|call me|phone me)\b", re.IGNORECASE)
_CLINICAL = re.compile(
    r"\b(diagnos|prescrib|prescription|dosage|should i take|what (medicine|drug|pill)|"
    r"change (my )?medication|treat my|is this cancer)\b", re.IGNORECASE)
_ADMIN = re.compile(
    r"\b(questionnaires?|forms?\b|slot|availability|available|book|booking|reschedul|cancel|"
    r"appointment|reminder|hospital|doctor|visit|upcoming|pending)\b", re.IGNORECASE)


async def run(state: dict) -> dict:
    from app.ai_assistant.prompts.system import SAFETY_SYSTEM
    from app.ai_assistant.services import llm as llm_mod

    text = ""
    for m in reversed(state.get("messages", [])):
        if m.get("role") == "user":
            text = m.get("content", "")
            break
    verdict, reason = "allow", "ok"
    try:
        res = await llm_mod.generate([{"role": "user", "content": text[:2000]}],
                                     system=SAFETY_SYSTEM)
        try:
            data = json.loads(res.content)
        except Exception:
            s, e = res.content.find("{"), res.content.rfind("}")
            data = json.loads(res.content[s:e + 1]) if s >= 0 and e > s else {}
        verdict = str(data.get("verdict", "allow"))
        reason = str(data.get("reason", "ok"))
        if verdict not in ("allow", "deny", "escalate"):
            verdict = "allow"
    except Exception:
        raise
    if verdict == "allow":
        if _URGENT.search(text or ""):
            verdict, reason = "escalate", "urgent"
        elif _HUMAN.search(text or ""):
            verdict, reason = "escalate", "human_requested"
        elif _CLINICAL.search(text or ""):
            verdict, reason = "deny", "clinical"
    elif verdict == "deny" and not _CLINICAL.search(text or "") and _ADMIN.search(text or ""):
        # LLM over-labels admin work (questionnaires, scheduling) as clinical —
        # product definition says these are administrative. Clinical phrasing keeps deny.
        verdict, reason = "allow", "admin_override"
    trace = [*state.get("trace", []), f"safety:{verdict}/{reason}"]
    return {"safety": {"verdict": verdict, "reason_category": reason}, "trace": trace}


def route_after_safety(state: dict) -> str:
    verdict = (state.get("safety") or {}).get("verdict", "deny")
    reason = (state.get("safety") or {}).get("reason_category", "")
    if verdict == "escalate":
        return "human_transfer"
    if verdict == "deny":
        return "human_transfer" if reason == "urgent" else "response"
    return "scope"
