"""Phase 8: AI layer unit tests — fail-closed LLM, MCP validation, routing, graph shape, DB roundtrip."""
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app import models


def _db():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def test_ai_tables_registered_and_roundtrip():
    for t in ("ai_conversations", "ai_messages", "ai_contexts",
              "capability_defs", "capability_executions", "ai_evaluations"):
        assert t in Base.metadata.tables
    db = _db()
    u = models.User(email="ai_t@example.org", role="patient", password_hash="x")
    db.add(u)
    db.commit()
    p = models.Patient(full_name="AI T"); db.add(p); db.commit()
    u.patient_id = p.id; db.commit()
    c = models.AIConversation(user_id=u.id, channel="web", correlation_id="test123")
    db.add(c); db.commit(); db.refresh(c)
    db.add(models.AIMessage(conversation_id=c.id, role="user", content="hi"))
    db.add(models.AIMessage(conversation_id=c.id, role="assistant", content="hello"))
    db.add(models.AIContext(conversation_id=c.id, conversational='{"summary": "greeting"}'))
    db.commit()
    roles = [m.role for m in db.query(models.AIMessage)
             .filter(models.AIMessage.conversation_id == c.id).order_by(models.AIMessage.id).all()]
    assert roles == ["user", "assistant"]


async def test_llm_fail_closed_no_keys(monkeypatch):
    from app.ai_assistant.services import llm as llm_mod
    from app.core.config import settings

    monkeypatch.setattr(settings, "INCEPTION_API_KEY", "")
    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    assert llm_mod.llm_status()["primary_configured"] is False
    with pytest.raises(llm_mod.AINotAvailable):
        await llm_mod.generate([{"role": "user", "content": "hi"}])


def test_mcp_adapter_validation():
    from app.ai_assistant.mcp import adapter

    assert len(adapter.known_tools()) == 23
    _, err = adapter.validate("nope", {})
    assert "Unknown capability" in err
    _, err = adapter.validate("create_appointment", {"hospital_id": 1})
    assert "Missing required arguments" in err and "doctor_id" in err
    coerced, err = adapter.validate("check_availability", {"doctor_id": "3"})
    assert err == "" and coerced["doctor_id"] == 3
    _, err = adapter.validate("check_availability", {"doctor_id": "abc"})
    assert "must be an integer" in err


def test_router_prompt_lists_all_tools():
    from app.ai_assistant.mcp import adapter
    from app.ai_assistant.prompts.system import ROUTER_SYSTEM

    prompt = ROUTER_SYSTEM.replace("__CATALOG__", ", ".join(adapter.known_tools()))
    for t in adapter.known_tools():
        assert t in prompt


def test_routing_functions():
    from app.ai_assistant.nodes import safety, scope, clarification, tool_router, tool_result

    assert safety.route_after_safety({"safety": {"verdict": "allow"}}) == "scope"
    assert safety.route_after_safety({"safety": {"verdict": "escalate"}}) == "human_transfer"
    assert safety.route_after_safety({"safety": {"verdict": "deny", "reason_category": "urgent"}}) == "human_transfer"
    assert safety.route_after_safety({"safety": {"verdict": "deny", "reason_category": "clinical"}}) == "response"
    assert scope.route_after_scope({"scope_hint": "unrelated"}) == "response"
    assert scope.route_after_scope({"scope_hint": ""}) == "clarification"
    assert clarification.route_after_clarification({"pending_clarification_fields": ["date_hint"]}) == "response"
    assert clarification.route_after_clarification({"pending_clarification_fields": [], "intent": "book"}) == "tool_router"
    assert tool_router.route_after_router({"selected_tool": "search_doctors"}) == "result"
    assert tool_router.route_after_router({"selected_tool": ""}) == "response"


def test_result_loop_routing():
    from app.ai_assistant.nodes import tool_result

    assert tool_result.route_after_result(
        {"chain_hint": "after search_doctors", "hop_count": 1, "tool_status": "ok"}) == "tool_router"
    assert tool_result.route_after_result(
        {"chain_hint": "", "hop_count": 1, "tool_status": "ok"}) == "response"
    assert tool_result.route_after_result(
        {"chain_hint": "x", "hop_count": 5, "tool_status": "ok"}) == "response"
    assert tool_result.route_after_result(
        {"chain_hint": "x", "hop_count": 1, "tool_status": "failed"}) == "response"


def test_graph_has_11_nodes_and_loop():
    from app.ai_assistant.graph.graph import get_graph

    g = get_graph().get_graph()
    nodes = set(g.nodes.keys()) - {"__start__", "__end__"}
    assert nodes == {"conversation", "context", "classify", "safety_check", "scope",
                     "clarification", "tool_router", "result", "human_transfer",
                     "response", "memory"}
    edges = {(e.source, e.target) for e in g.edges}
    assert ("result", "tool_router") in edges
    assert ("response", "memory") in edges
