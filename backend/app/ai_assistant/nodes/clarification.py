"""clarification node: purely LLM-driven missing-field detection.

No _NEEDS table, no slot-follow-up regex, no surname heuristics.
The LLM inspects intent + entities + catalog and returns what to ask.
A thin deterministic lookup resolves a named doctor to IDs (data lookup,
works in any language — not a language rule).
"""
from __future__ import annotations

import json


def _resolve_doctor_by_name(state: dict, name: str) -> dict:
    """Global name -> {doctor_id, doctor_name} via token containment.

    No length thresholds, no word-boundary regex, no language lists:
    every token of the stored name must appear in the message or vice versa.
    """
    try:
        rt = state.get("_runtime", {}) or {}
        db = rt.get("db")
        if db is None or not name:
            return {}
        from app.models import Doctor as _D

        rows = db.query(_D).filter(_D.status == "active").all()
        from app.ai_assistant.mcp.registry import clean_tokens
        needle_tokens = clean_tokens(name)
        if not needle_tokens:
            return {}
        best: dict = {}
        best_score = 0
        for d in rows:
            hay = f" {(d.name or '').lower()} "
            score = sum(1 for t in needle_tokens if t and t in hay)
            if score > best_score:
                best_score = score
                best = {"doctor_id": d.id, "doctor_name": d.name}
        # Require at least one token hit; prefer full-name matches via score.
        return best if best_score > 0 else {}
    except Exception:
        return {}


async def run(state: dict) -> dict:
    from app.ai_assistant.mcp import adapter
    from app.ai_assistant.mcp import registry as reg
    from app.ai_assistant.prompts.system import CLARIFY_SYSTEM
    from app.ai_assistant.services import llm as llm_mod

    intent = state.get("intent", "ambiguous")
    cls = state.get("classification") or {}
    ctx = state.get("context_refs") or {}
    tx = ctx.get("transactional") or {}
    if isinstance(tx, str):
        try:
            tx = json.loads(tx)
        except Exception:
            tx = {}

    # Data enrichment (any intent): a named doctor/hospital without an id is
    # resolved generically via the registry helper — no intent branches.
    out_extra: dict = {}
    last_user = ""
    for m in reversed(state.get("messages", []) or []):
        if isinstance(m, dict) and m.get("role") == "user":
            last_user = str(m.get("content", ""))
            break
    named = (cls.get("doctor_name") or tx.get("doctor_name") or "").strip()
    if named and not tx.get("doctor_id"):
        hit = _resolve_doctor_by_name(state, named or last_user)
        if not hit and last_user:
            hit = _resolve_doctor_by_name(state, last_user)
        if hit:
            tx2 = dict(tx)
            tx2.setdefault("doctor_name", hit["doctor_name"])
            tx2.setdefault("doctor_id", hit["doctor_id"])
            refs = dict(ctx)
            refs["transactional"] = tx2
            out_extra["context_refs"] = refs
            tx = tx2

    from app.ai_assistant import orchestration as orch
    _names, catalog = orch.build_catalog()
    prompt = (
        f"Intent: {intent}\nClassification: {json.dumps(cls)[:1000]}\n"
        f"Transactional: {json.dumps(tx)[:800]}\n"
        f"Last user: {last_user[:800]}\n"
        f"Tools:\n{catalog}\nJSON:"
    )
    try:
        res = await llm_mod.generate([{"role": "user", "content": prompt}], system=CLARIFY_SYSTEM)
        try:
            data = json.loads(res.content)
        except Exception:
            s, e = res.content.find("{"), res.content.rfind("}")
            data = json.loads(res.content[s:e + 1]) if s >= 0 and e > s else {}
        missing = data.get("missing", []) if isinstance(data.get("missing", []), list) else []
    except Exception:
        raise
    missing = [str(m) for m in missing if str(m).strip()]
    trace = [*state.get("trace", []),
             f"clarification:{','.join(missing) if missing else 'complete'}"]
    return {"pending_clarification_fields": missing, "trace": trace, **out_extra}


def route_after_clarification(state: dict) -> str:
    if state.get("pending_clarification_fields"):
        return "response"
    if state.get("intent") in ("greeting",):
        return "response"
    return "tool_router"
