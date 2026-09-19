"""Safety node: hard control layer (runs before scope/tools).

Order: deterministic policy → human-request fast path → LLM second signal
(combined so deterministic deny/escalate always wins). Sets state["safety"].
Never calls tools, never generates the final reply here.
"""
from __future__ import annotations

from ..safety import policy, rules


async def run(state: dict) -> dict:
    rt = state.get("_runtime", {}) or {}
    messages = state.get("messages", []) or []
    text = messages[-1].get("content", "") if messages else rt.get("text", "")

    verdict = policy.check(text)
    if verdict["verdict"] == "allow" and policy.wants_human(text):
        verdict = {"verdict": "escalate", "reason_category": "human_requested"}
    if verdict["verdict"] == "allow":
        llm = rt.get("llm")
        second = None
        if llm is not None and getattr(llm, "name", "") != "deterministic":
            try:
                second = (await llm.safety_review(text)).model_dump()
            except Exception:
                second = None
        verdict = rules.triage(text, second)

    table = {"allow": "allow", "deny": "deny", "escalate": "escalate"}
    return {
        "safety": {"verdict": table.get(verdict.get("verdict"), "deny"),
                   "reason_category": verdict.get("reason_category", "")},
        "trace": [*state.get("trace", []),
                  f"safety: {verdict.get('verdict')}/{verdict.get('reason_category')}"],
    }


def route_after_safety(state: dict) -> str:
    """deny + urgent/human → human_transfer; other deny → response; else scope."""
    verdict = (state.get("safety") or {}).get("verdict", "deny")
    reason = (state.get("safety") or {}).get("reason_category", "")
    if verdict == "deny":
        return "human_transfer" if reason in ("urgent",) else "response"
    if verdict == "escalate":
        return "human_transfer"
    return "scope"
