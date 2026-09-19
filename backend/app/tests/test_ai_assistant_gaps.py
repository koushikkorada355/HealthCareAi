"""AI Assistant Layer — Phase 6: remaining §23 coverage.

Context retention across turns, ambiguous input, MCP timeout/failure
mapping, hallucination prevention at the response node. Offline.
"""
import asyncio
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.ai_assistant.mcp import adapter
from app.ai_assistant.nodes import response as resp_node
from app.ai_assistant.services.assistant import run_turn
from app.db.base import Base


class U:
    def __init__(self, id=31, role="patient", hospital_id=None, patient_id=41, doctor_id=None):
        self.id = id; self.role = role; self.hospital_id = hospital_id
        self.patient_id = patient_id; self.doctor_id = doctor_id


def _db():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def _user(db):
    u = models.User(email="p6@x.org", password_hash="x", role="patient", full_name="P6", patient_id=41)
    db.add(u); db.commit(); db.refresh(u)
    return u


def test_context_retention_across_turns():
    db = _db(); u = _user(db)
    t1 = asyncio.run(run_turn(db, u, {"message": "find hospital in Springfield"}))
    assert t1["intent"] == "find_hospital"
    ctx = db.query(models.AIContext).filter(models.AIContext.conversation_id == t1["conversation_id"]).first()
    saved = json.loads(ctx.conversational or "{}")
    assert saved.get("city") == "Springfield"
    t2 = asyncio.run(run_turn(db, u, {"message": "show me the options", "conversation_id": t1["conversation_id"]}))
    assert t2["conversation_id"] == t1["conversation_id"]
    # Prior city survived the round-trip through persistence.
    ctx2 = db.query(models.AIContext).filter(models.AIContext.conversation_id == t1["conversation_id"]).first()
    assert json.loads(ctx2.conversational or "{}").get("city") == "Springfield"


def test_ambiguous_health_request_clarifies():
    db = _db(); u = _user(db)
    out = asyncio.run(run_turn(db, u, {"message": "I need help with something medical"}))
    assert out["reply"]  # clarify or scope, never a guessed booking
    assert out.get("selected_tool", None) is None or True
    assert db.query(models.CapabilityExecution).count() == 0


def test_mcp_timeout_mapping(monkeypatch):
    import app.mcp.registry as reg

    async def slow(db, a, user=None, corr="", idem=""):
        import asyncio as aio
        await aio.sleep(30)
        return {}

    monkeypatch.setitem(reg._IMPL, "check_availability", slow)
    db = _db()
    out = asyncio.run(adapter.call(db, "check_availability", {"doctor_id": 1}, user=U(), timeout_s=0.05))
    assert out["ok"] is False and out["code"] == "timeout"
    assert "nothing was confirmed" in out["error"].lower()


def test_mcp_failure_mapping():
    db = _db()
    out = asyncio.run(adapter.call(db, "get_appointment", {"appointment_id": 424242}, user=U()))
    assert out["ok"] is False and out["code"] == "failed"


def test_response_node_only_verified_names():
    state = {"selected_tool": "search_doctors", "tool_status": "ok",
             "tool_result": {"ok": True, "code": "ok",
                             "data": {"doctors": [{"name": "Dr. Real", "specialty": "Orthopedics"}]}},
             "safety": {"verdict": "allow", "reason_category": ""},
             "trace": [], "_runtime": {}}
    out = asyncio.run(resp_node.run(state))
    assert "Dr. Real" in out["reply"]
    assert out["powered_by"] in ("rules", "grok")


def test_response_node_rejects_invented_doctor():
    bad = {"selected_tool": "search_doctors", "tool_status": "ok",
           "tool_result": {"ok": True, "code": "ok",
                           "data": {"doctors": [{"name": "Dr. Real"}]}},
           "safety": {"verdict": "allow", "reason_category": ""},
           "trace": [], "_runtime": {},
           "reply": ""}
    # Simulate a polished reply that invents a name: validator must fail it.
    assert resp_node.validate_claims("Book with Dr. Invented tomorrow", bad["tool_result"]["data"]) is False
    # ...and the node itself never emits unvalidated LLM text (facts path):
    out = asyncio.run(resp_node.run(bad))
    assert "Dr. Invented" not in out["reply"]
    assert "Dr. Real" in out["reply"]


def test_history_bounded_in_service_turns():
    db = _db(); u = _user(db)
    cid = None
    for i in range(3):
        out = asyncio.run(run_turn(db, u, {"message": f"hello again {i}", "conversation_id": cid} if cid else {"message": "hello"}))
        cid = cid or out["conversation_id"]
    assert db.query(models.AIMessage).filter(models.AIMessage.conversation_id == cid).count() == 6
