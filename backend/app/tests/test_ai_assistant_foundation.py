"""AI Assistant Layer — Phase 1: schemas, config, LLM interface + fallback.

Offline-safe: no keys, no DB, no network.
"""
import asyncio

from app.ai_assistant import config as cfg
from app.ai_assistant.schemas.agent import (
    AgentResponse,
    Classification,
    PendingConfirmation,
    SafetyVerdict,
    ToolCall,
)
from app.ai_assistant.services.llm import DeterministicLLM, GrokLLM, get_llm


def test_config_defaults_offline():
    assert cfg.HISTORY_WINDOW == 10
    assert cfg.SUMMARY_THRESHOLD == 20
    assert cfg.MCP_TIMEOUT_S > 0
    assert cfg.LLM_TIMEOUT_S > 0


def test_schemas_validate():
    c = Classification(category="administrative", intent="book", entities={"specialty": "orthopedics"}, confidence=0.9)
    assert c.intent == "book" and not c.needs_action_write
    v = SafetyVerdict(verdict="deny", reason_category="clinical")
    assert v.verdict == "deny"
    t = ToolCall(name="search_doctors", args={"specialty": "orthopedics"}, tool_call_id="abc123")
    assert t.tool_call_id == "abc123"
    p = PendingConfirmation(tool="create_appointment", args={}, idempotency_key="k", summary="s")
    assert p.tool == "create_appointment"
    r = AgentResponse(reply="hi", trace=["a"], data={}, powered_by="rules", graph_run_id="g", safety={})
    assert r.powered_by == "rules"


def test_schemas_reject_bad_values():
    import pytest
    from pydantic import ValidationError
    with pytest.raises(ValidationError):
        Classification(category="administrative", intent="book", confidence=1.5)
    with pytest.raises(ValidationError):
        SafetyVerdict(verdict="maybe", reason_category="x")


def test_llm_factory_offline_is_deterministic(monkeypatch):
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    llm = get_llm()
    assert isinstance(llm, DeterministicLLM)
    assert llm.name == "deterministic"


def _classify(text):
    return asyncio.run(DeterministicLLM().classify(text))


def test_fallback_parity_book():
    c = _classify("I need to see a doctor for my shoulder pain sometime this week.")
    assert c.category == "administrative" and c.intent == "book"
    assert c.entities.get("specialty") == "orthopedics"


def test_fallback_parity_vague_is_ambiguous():
    c = _classify("I need to see a doctor.")
    assert c.intent in ("book", "unknown")
    assert c.category in ("administrative", "ambiguous")


def test_fallback_parity_unsafe_is_clinical():
    c = _classify("diagnose me, what do I have?")
    assert c.category == "clinical"


def test_fallback_parity_greeting():
    c = _classify("hello")
    assert c.category == "administrative" and c.intent == "greeting"


def test_fallback_parity_unrelated():
    c = _classify("tell me a joke about cats")
    assert c.category == "unrelated" and c.intent == "unknown"


def test_fallback_parity_confirmation_and_decline():
    assert _classify("yes, book it").intent == "confirm"
    assert _classify("yes, book it").needs_action_write is True
    assert _classify("no, never mind").intent == "decline"


def test_fallback_entities_city_appointment():
    c = _classify("find hospital in Springfield for appointment #42")
    assert c.entities.get("city") == "Springfield"
    assert c.entities.get("appointment_id") == 42


def test_deterministic_rephrase_is_passthrough():
    out, used = asyncio.run(DeterministicLLM().rephrase("facts here"))
    assert out == "facts here" and used is False


def test_deterministic_safety_review_is_neutral():
    v = asyncio.run(DeterministicLLM().safety_review("anything"))
    assert isinstance(v, SafetyVerdict) and v.verdict == "allow"


def test_grok_llm_shape_without_key(monkeypatch):
    monkeypatch.delenv("GROK_API_KEY", raising=False)
    llm = GrokLLM()
    assert llm.name == "grok"
    c = asyncio.run(llm.classify("hello"))
    assert isinstance(c, Classification)
    v = asyncio.run(llm.safety_review("hello"))
    assert isinstance(v, SafetyVerdict)
