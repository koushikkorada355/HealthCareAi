"""Fail-closed LLM client: Mercury 2.5 primary, gpt-oss-120b fallback.

No deterministic rules. No keys / both providers down -> AINotAvailable
and the API must return 503 ai_unavailable without fabricating a reply.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass


class AINotAvailable(Exception):
    pass


FAILURE_MESSAGE = "AI unavailable — configure INCEPTION_API_KEY"


@dataclass
class LLMResult:
    content: str
    powered_by: str
    latency_ms: int


def llm_status() -> dict:
    from app.core.config import settings

    primary = bool((settings.INCEPTION_API_KEY or "").strip())
    fallback = bool((settings.GROQ_API_KEY or "").strip())
    return {
        "primary_configured": primary,
        "fallback_configured": fallback,
        "primary_model": settings.INCEPTION_MODEL,
        "fallback_model": settings.GROQ_MODEL,
    }


def _make_client(kind: str):
    from app.core.config import settings

    try:
        from langchain_openai import ChatOpenAI
    except Exception as e:
        raise AINotAvailable(FAILURE_MESSAGE) from e
    if kind == "primary":
        key = (settings.INCEPTION_API_KEY or "").strip()
        if not key:
            return None
        return ChatOpenAI(
            model=settings.INCEPTION_MODEL,
            api_key=key,
            base_url=settings.INCEPTION_BASE_URL,
            timeout=settings.LLM_TIMEOUT_S,
            temperature=0.4,
        )
    key = (settings.GROQ_API_KEY or "").strip()
    if not key:
        return None
    return ChatOpenAI(
        model=settings.GROQ_MODEL,
        api_key=key,
        base_url=settings.GROQ_BASE_URL,
        timeout=settings.LLM_TIMEOUT_S,
        temperature=0.4,
    )


async def _invoke(client, messages: list) -> str:
    resp = await client.ainvoke(messages)
    text = getattr(resp, "content", "") or ""
    if isinstance(text, list):
        text = "".join(getattr(p, "text", str(p)) for p in text)
    return str(text).strip()


async def generate(messages: list, system: str = "") -> LLMResult:
    """Single LLM text call. messages: [{role, content}] or [(role, content)]."""
    norm = []
    if system:
        norm.append(("system", system))
    for m in messages:
        if isinstance(m, (list, tuple)) and len(m) == 2:
            norm.append((m[0], m[1]))
        elif isinstance(m, dict) and m.get("content"):
            norm.append((m.get("role", "user"), m["content"]))
    errors: list[str] = []
    for kind, name in (("primary", None), ("fallback", None)):
        client = _make_client(kind)
        if client is None:
            errors.append(f"{kind}: no key")
            continue
        t0 = time.time()
        try:
            text = await _invoke(client, norm)
            if not text:
                raise RuntimeError("empty reply")
            from app.core.config import settings

            powered = settings.INCEPTION_MODEL if kind == "primary" else settings.GROQ_MODEL
            return LLMResult(content=text, powered_by=powered, latency_ms=int((time.time() - t0) * 1000))
        except Exception as e:
            errors.append(f"{kind}: {type(e).__name__}: {str(e)[:200]}")
            continue
    raise AINotAvailable(f"{FAILURE_MESSAGE} ({'; '.join(errors)})")


def _extract_json(text: str) -> dict:
    try:
        return json.loads(text)
    except Exception:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start >= 0 and end > start:
        try:
            return json.loads(text[start : end + 1])
        except Exception:
            pass
    return {}


CLASSIFY_SYSTEM = (
    "You are a medical admin intake classifier. Reply with JSON only: "
    '{"intent": "book|reschedule|cancel|lookup|questionnaire|admin_q|greeting|unsupported|unrelated|ambiguous", '
    '"category": "clinical|admin|unrelated|unsupported|ambiguous", '
    '"specialty": "", "urgency": "routine|urgent", "dates": "", "safety_flag": ""}. '
    "Never diagnose. Never invent IDs."
)


async def classify(text: str, history: str = "") -> dict:
    """LLM classification. Raises AINotAvailable when LLM is down."""
    prompt = f"History summary: {history[:800]}\nPatient message: {text[:2000]}\nJSON:"
    res = await generate([{"role": "user", "content": prompt}], system=CLASSIFY_SYSTEM)
    data = _extract_json(res.content)
    return {
        "intent": str(data.get("intent", "ambiguous")),
        "category": str(data.get("category", "ambiguous")),
        "specialty": str(data.get("specialty", "")),
        "urgency": str(data.get("urgency", "routine")),
        "dates": str(data.get("dates", "")),
        "safety_flag": str(data.get("safety_flag", "")),
        "powered_by": res.powered_by,
        "latency_ms": res.latency_ms,
    }


GATE_SYSTEM = (
    "You decide if new chat turns add important durable facts (new intent, "
    "entity change, decision, verified booking/cancel/reschedule, new dates, "
    "doctor/hospital change, safety/escalation flag, pending confirmation set "
    "or cleared). Greetings, thanks, repeats are NOT important. Reply JSON only: "
    '{"important": true|false, "reason": ""}.'
)


async def importance_gate(summary: str, new_texts: list[str]) -> bool:
    try:
        res = await generate(
            [{"role": "user", "content": f"Summary: {summary[:1000]}\nNew: {' | '.join(new_texts)[:1500]}\nJSON:"}],
            system=GATE_SYSTEM,
        )
        return bool(_extract_json(res.content).get("important", False))
    except AINotAvailable:
        raise
    except Exception:
        return False


SUMMARIZE_SYSTEM = (
    "Rewrite the rolling chat summary in <=150 words: keep intents, entities "
    "(specialty, hospital/doctor refs, dates), decisions, verified outcomes, "
    "pending items, safety flags. Drop greetings/small-talk. Minimize PHI. "
    "Never add diagnoses or invented IDs. Reply plain text only."
)


async def rewrite_summary(old: str, new_texts: list[str]) -> str:
    res = await generate(
        [{"role": "user", "content": f"Old summary: {old[:1200]}\nNew turns: {' | '.join(new_texts)[:2000]}\nRewrite:"}],
        system=SUMMARIZE_SYSTEM,
    )
    return res.content[:1200]


ENTITY_SYSTEM = (
    "Extract durable booking entities from recent chat turns. Reply JSON only: "
    '{"doctor_id": 0, "doctor_name": "", "hospital_id": 0, "hospital_name": "", '
    '"specialty": "", "date_iso": "", "time_window": ""}. '
    "Tool-result turns list doctors/hospitals WITH their IDs — copy the ID of the "
    "entry matching the named doctor/hospital (prefer same-hospital matches). "
    "Dates as YYYY-MM-DD when stated; time_window morning|afternoon|evening. "
    "Never invent IDs."
)


async def extract_entities(turns: list[str], prior: dict) -> dict:
    """LLM entity extraction merged over prior transactional (no hardcode)."""
    try:
        res = await generate(
            [{"role": "user",
              "content": f"Prior: {json.dumps(prior)[:800]}\nTurns: {' | '.join(turns)[:2000]}\nJSON:"}],
            system=ENTITY_SYSTEM,
        )
        data = _extract_json(res.content)
    except AINotAvailable:
        raise
    except Exception:
        return {}
    merged = dict(prior or {})
    for k in ("doctor_id", "doctor_name", "hospital_id", "hospital_name",
              "specialty", "date_iso", "time_window"):
        v = data.get(k)
        if v not in (None, "", 0, "0"):
            merged[k] = v
    return merged
