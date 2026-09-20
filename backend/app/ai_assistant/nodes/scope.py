"""scope node: unrelated/unsupported end here with a hint (LLM words it)."""
from __future__ import annotations


async def run(state: dict) -> dict:
    category = (state.get("classification") or {}).get("category", "ambiguous")
    if category in ("unrelated", "unsupported"):
        trace = [*state.get("trace", []), f"scope:{category}"]
        return {"scope_hint": category, "trace": trace}
    trace = [*state.get("trace", []), f"scope:{category or 'in-scope'}"]
    return {"scope_hint": "", "trace": trace}


def route_after_scope(state: dict) -> str:
    if state.get("scope_hint"):
        return "response"
    return "clarification"
