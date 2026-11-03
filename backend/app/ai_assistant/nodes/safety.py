"""safety node: purely LLM-driven verdict, no keyword/regex lists.

The LLM decides allow|deny|escalate in any language. Code only persists
the verdict and routes — never overrides wording with hardcoded patterns.
Fail-closed: LLM down raises (handled upstream as 503, no fabricated reply).
"""
from __future__ import annotations

import json


async def run(state: dict) -> dict:
    from app.ai_assistant.prompts.system import SAFETY_SYSTEM
    from app.ai_assistant.services import llm as llm_mod

    text = ""
    for m in reversed(state.get("messages", [])):
        if m.get("role") == "user":
            text = m.get("content", "")
            break
    verdict, reason = "allow", "ok"
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
