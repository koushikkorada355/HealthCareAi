"""Provider-independent LLM interface for the AI Assistant Layer.

- `BaseLLM`: contract used by graph nodes (classify / safety_review / rephrase).
- `GrokLLM`: OpenAI-compatible structured calls (JSON mode), graceful None-paths.
- `DeterministicLLM`: offline fallback reusing the existing keyword interpreter
  (`app.ai.graph`) mapped onto the new Classification schema.
- `get_llm()`: Grok when configured, else deterministic. Nodes never branch
  on provider — they branch on schema validity.
"""
from __future__ import annotations

import json
import re

from .. import config
from ..prompts import classification as cls_prompts
from ..prompts import response as resp_prompts
from ..prompts import safety as saf_prompts
from ..schemas.agent import Classification, SafetyVerdict

_INTENT_TO_WRITE = {"reschedule", "cancel", "confirm", "escalate", "submit"}

_SPEC_KEYWORDS = {
    "shoulder": "orthopedics", "knee": "orthopedics", "bone": "orthopedics",
    "fracture": "orthopedics", "skin": "dermatology", "rash": "dermatology",
    "heart": "cardiology", "chest": "cardiology", "child": "pediatrics",
    "eye": "ophthalmology", "tooth": "dental", "teeth": "dental",
    "mental": "psychiatry", "pregnan": "gynecology", "headache": "neurology",
    "migraine": "neurology",
}
_SPEC_WORD_RE = re.compile(
    r"\b(cardiology|orthopedics|dermatology|neurology|pediatrics|general|gynecology|ophthalmology|ent|dental|psychiatry|oncology)\b",
    re.IGNORECASE,
)


def _spec_from_words(text: str) -> str:
    """Specialty extraction without the legacy substring quirk.

    The legacy matcher substring-scans SPECS, so "appointm**ent**" becomes
    specialty "ent". Here keywords stay substring (symptom phrases need it)
    but specialty names require word boundaries.
    """
    t = (text or "").lower()
    for k, v in _SPEC_KEYWORDS.items():
        if k in t:
            return v
    m = _SPEC_WORD_RE.search(text or "")
    return m.group(1).lower() if m else ""


_CITY_RE = re.compile(r"\bin\s+([A-Z][a-zA-Z\-]*(?:\s+[A-Z][a-zA-Z\-]*){0,2})")
_CITY_LOWER_RE = re.compile(r"\bin\s+([a-z]+)")
_APPT_RE = re.compile(r"(?:appointment|appt|booking)?\s*#\s*(\d{1,8})", re.IGNORECASE)
_ISO_RE = re.compile(r"\d{4}-\d{2}-\d{2}[T ]\d{2}:\d{2}")
_CONFIRM_RE = re.compile(
    r"^\s*(yes|yeah|yep|yup|sure|ok|okay|confirm(?:ed)?|book it|go ahead|proceed|do it|please (?:do|book|confirm|proceed))[\s.!]*$",
    re.IGNORECASE,
)
_CONFIRM_PREFIX_RE = re.compile(
    r"^\s*(yes|yeah|yep|sure|ok|okay)[,\s]+(book it|confirm|go ahead|proceed|do it|please (?:book|confirm|proceed)).*$",
    re.IGNORECASE,
)
_DECLINE_RE = re.compile(
    r"^\s*(no|nope|nah|cancel that|stop|never mind|not now|don't|dont|no,? (?:never mind|thanks|thank you|thanks though))[\s.!]*$",
    re.IGNORECASE,
)
_HEALTH_HINT_RE = re.compile(
    r"hospital|doctor|clinic|appoint|slot|book|health|medical|symptom|pain|doctor|pharmacy|prescri|diagnos|questionnaire|availab|resched|cancel|specialist",
    re.IGNORECASE,
)


class BaseLLM:
    """Contract every provider implements."""

    name = "base"

    async def classify(self, text: str, history: str = "") -> Classification:
        raise NotImplementedError

    async def safety_review(self, text: str) -> SafetyVerdict:
        raise NotImplementedError

    async def rephrase(self, facts: str) -> tuple[str, bool]:
        """Return (wording, used_llm). Never invents: input is pre-verified facts."""
        raise NotImplementedError


def _extract_entities(text: str, base: dict | None = None) -> dict:
    ent: dict = dict(base or {})
    low = text.lower()
    m = _CITY_RE.search(text) or _CITY_LOWER_RE.search(low)
    if m and not ent.get("city"):
        ent["city"] = m.group(1).strip().title()
    m = _APPT_RE.search(text)
    if m and not ent.get("appointment_id"):
        try:
            ent["appointment_id"] = int(m.group(1))
        except (TypeError, ValueError):
            pass
    m = _ISO_RE.search(text)
    if m and not ent.get("slot_iso"):
        ent["slot_iso"] = m.group(0)
    return ent


class DeterministicLLM(BaseLLM):
    """Offline fallback: existing keyword interpreter mapped to the schema."""

    name = "deterministic"

    def classify_sync(self, text: str, history: str = "") -> Classification:
        from app.ai.graph import run_graph

        t = (text or "").strip()
        if _CONFIRM_RE.match(t) or _CONFIRM_PREFIX_RE.match(t):
            return Classification(category="administrative", intent="confirm",
                                  entities=_extract_entities(text), confidence=0.9,
                                  needs_action_write=True)
        if _DECLINE_RE.match(t):
            return Classification(category="administrative", intent="decline",
                                  entities=_extract_entities(text), confidence=0.85,
                                  needs_action_write=False)
        g = run_graph(text, {})
        intent = g.get("intent", "unknown") or "unknown"
        spec = _spec_from_words(text)
        if intent == "unknown" and spec:
            # "Cardiology." answering a clarification is a doctor search,
            # not an unrelated turn.
            return Classification(category="administrative", intent="find_doctor",
                                  entities=_extract_entities(text, {"specialty": spec}),
                                  confidence=0.7, needs_action_write=False)
        if intent == "unsafe":
            return Classification(category="clinical", intent="unsafe",
                                  entities=_extract_entities(text), confidence=0.9,
                                  needs_action_write=False)
        if intent == "unknown":
            category = "ambiguous" if _HEALTH_HINT_RE.search(text) else "unrelated"
            return Classification(category=category, intent="unknown",  # type: ignore[arg-type]
                                  entities=_extract_entities(text), confidence=0.5,
                                  needs_action_write=False)
        if intent == "greeting":
            return Classification(category="administrative", intent="greeting",
                                  entities={}, confidence=0.95, needs_action_write=False)
        entities = _extract_entities(text, {"specialty": spec,
                                            "date_pref": g.get("date_pref", "")})
        return Classification(category="administrative", intent=intent, entities=entities,
                              confidence=0.8, needs_action_write=intent in _INTENT_TO_WRITE)

    async def classify(self, text: str, history: str = "") -> Classification:
        return self.classify_sync(text, history)

    async def safety_review(self, text: str) -> SafetyVerdict:  # type: ignore[override]
        # Neutral by design: the deterministic policy (safety/policy.py) is
        # authoritative; this second signal only refines allow-cases via LLM.
        return SafetyVerdict(verdict="allow", reason_category="", detail="")

    async def rephrase(self, facts: str) -> tuple[str, bool]:
        return facts, False


class GrokLLM(BaseLLM):
    """Grok (or any OpenAI-compatible) structured calls with safe fallbacks."""

    name = "grok"

    def __init__(self) -> None:
        self._fallback = DeterministicLLM()

    async def _chat_json(self, system: str, user: str) -> dict | None:
        try:
            from openai import AsyncOpenAI
            import os

            client = AsyncOpenAI(api_key=os.getenv("GROK_API_KEY", "").strip(),
                                 base_url=os.getenv("GROK_BASE_URL", "https://api.x.ai/v1"),
                                 timeout=config.LLM_TIMEOUT_S)
            shots = "\n".join(f"User: {u}\nJSON: {json.dumps(j)}" for u, j in cls_prompts.FEW_SHOTS)
            r = await client.chat.completions.create(
                model=os.getenv("GROK_MODEL", "grok-3-mini"),
                messages=[{"role": "system", "content": system},
                          {"role": "user", "content": f"{shots}\nUser: {user}\nJSON:"}],
                max_tokens=config.LLM_CLASSIFY_MAX_TOKENS,
                temperature=config.LLM_CLASSIFY_TEMPERATURE,
                response_format={"type": "json_object"},
            )
            text = (r.choices[0].message.content or "").strip()
            parsed = json.loads(text)
            return parsed if isinstance(parsed, dict) else None
        except Exception:
            return None

    async def classify(self, text: str, history: str = "") -> Classification:
        from app.ai.grok_client import grok_configured

        if not grok_configured():
            return await self._fallback.classify(text, history)
        user = f"History: {history}\nMessage: {text}" if history else f"Message: {text}"
        parsed = await self._chat_json(cls_prompts.CLASSIFY_INSTRUCTIONS, user)
        if not parsed:
            return await self._fallback.classify(text, history)
        try:
            cls = Classification(**parsed)
        except Exception:
            return await self._fallback.classify(text, history)
        # Deterministic gap-fill: LLM often drops city/appointment/slot spans.
        merged = _extract_entities(text, dict(cls.entities or {}))
        cls.entities = merged
        return cls

    async def safety_review(self, text: str) -> SafetyVerdict:
        from app.ai.grok_client import grok_configured

        if not grok_configured():
            return SafetyVerdict(verdict="allow", reason_category="", detail="")
        parsed = await self._chat_json(saf_prompts.SAFETY_INSTRUCTIONS, f"Message: {text}")
        if not parsed:
            return SafetyVerdict(verdict="allow", reason_category="", detail="")
        try:
            v = SafetyVerdict(**parsed)
        except Exception:
            return SafetyVerdict(verdict="allow", reason_category="", detail="")
        if v.verdict not in ("allow", "deny", "escalate"):
            return SafetyVerdict(verdict="allow", reason_category="", detail="")
        v.detail = ""
        return v

    async def rephrase(self, facts: str) -> tuple[str, bool]:
        from app.ai.grok_client import grok_chat

        polished = await grok_chat(
            [{"role": "system", "content": resp_prompts.RESPONSE_INSTRUCTIONS},
             {"role": "user", "content": f"Rephrase helpfully (<=120 words). FACTS: {facts}"}])
        if polished:
            return polished, True
        return facts, False


def get_llm() -> BaseLLM:
    """Grok when a key is configured, else the deterministic fallback."""
    try:
        from app.ai.grok_client import grok_configured

        if grok_configured():
            return GrokLLM()
    except Exception:
        pass
    return DeterministicLLM()
