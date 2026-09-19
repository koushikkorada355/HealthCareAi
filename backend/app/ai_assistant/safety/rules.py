"""Safety helper rules (pure functions used by nodes/safety.py)."""
from __future__ import annotations

from . import policy


def triage(text: str, llm_verdict: dict | None = None) -> dict:
    """Combine deterministic policy with an optional LLM second signal.

    - Deterministic deny/escalate always wins.
    - LLM may only deny/escalate an otherwise-allowed turn, never allow a
      deterministically denied one.
    Returns {"verdict", "reason_category"}.
    """
    base = policy.check(text)
    if base["verdict"] in ("deny", "escalate") or not llm_verdict:
        return base
    lv = (llm_verdict.get("verdict") or "allow").strip().lower()
    if lv in ("deny", "escalate"):
        return {"verdict": lv,
                "reason_category": (llm_verdict.get("reason_category") or "llm").strip() or "llm"}
    return base


def refusal_for(reason_category: str) -> str:
    if reason_category == "urgent":
        return policy.urgent_response()
    if reason_category == "injection":
        return policy.injection_refusal()
    return policy.clinical_refusal()
