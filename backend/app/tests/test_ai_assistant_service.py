"""AI Assistant Layer — Phase 5: response validation, service, observability.

Offline except sqlite; deterministic LLM (no keys).
"""
import asyncio
import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.ai_assistant.nodes import response as resp_node
from app.ai_assistant.services.assistant import run_turn
from app.db.base import Base


class U:
    def __init__(self, id=11, role="patient", hospital_id=None, patient_id=21, doctor_id=None):
        self.id = id; self.role = role; self.hospital_id = hospital_id
        self.patient_id = patient_id; self.doctor_id = doctor_id


def _db():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def _user(db):
    u = models.User(email="v5@x.org", password_hash="x", role="patient", full_name="V5", patient_id=21)
    db.add(u); db.commit(); db.refresh(u)
    return u


def test_validate_claims_accepts_grounded():
    data = {"doctors": [{"name": "Dr. Maya Rao"}], "slots": [{"starts_at": "2026-09-21T10:00:00+00:00"}]}
    assert resp_node.validate_claims("**Dr. Maya Rao** at 2026-09-21 10:00", data) is True


def test_validate_claims_rejects_invented_slot():
    data = {"doctors": [{"name": "Dr. Maya Rao"}], "slots": [{"starts_at": "2026-09-21T10:00:00+00:00"}]}
    assert resp_node.validate_claims("Booked 2030-01-01 10:00 with Dr. Nope", data) is False


def test_validate_claims_rejects_clinical():
    assert resp_node.validate_claims("You should take ibuprofen, dosage 200mg", {"doctors": []}) is False


def test_service_turn_greeting_envelope_and_persistence():
    db = _db(); u = _user(db)
    out = asyncio.run(run_turn(db, u, {"message": "hello"}))
    assert out["intent"] == "greeting"
    assert out["reply"] and out["conversation_id"] and out["correlation_id"]
    assert out["graph_run_id"] and out["powered_by"] == "rules"
    assert out["safety"] == {"verdict": "allow", "reason_category": ""}
    assert out["route"] in ("answer", "clarify", "discover")
    assert db.query(models.AIMessage).filter(models.AIConversation.id == out["conversation_id"]).count() == 2
    ctx = db.query(models.AIContext).filter(models.AIContext.conversation_id == out["conversation_id"]).first()
    assert ctx is not None and "intent" in json.loads(ctx.conversational or "{}")


def test_service_turn_unsafe_refusal_no_tool_call():
    db = _db(); u = _user(db)
    out = asyncio.run(run_turn(db, u, {"message": "diagnose me please"}))
    assert out["safety"]["verdict"] == "deny"
    assert "diagnos" in out["reply"].lower()
    assert db.query(models.CapabilityExecution).count() == 0


def test_service_conversation_continuity_and_pending_roundtrip():
    db = _db(); u = _user(db)
    t1 = asyncio.run(run_turn(db, u, {"message": "I want to cancel my appointment"}))
    assert t1.get("route") in ("clarify", "answer")
    t2 = asyncio.run(run_turn(db, u, {"message": "appointment #7", "conversation_id": t1["conversation_id"]}))
    assert t2["conversation_id"] == t1["conversation_id"]
    assert db.query(models.AIMessage).filter(models.AIMessage.conversation_id == t1["conversation_id"]).count() == 4
