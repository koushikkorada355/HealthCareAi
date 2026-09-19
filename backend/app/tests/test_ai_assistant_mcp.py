"""AI Assistant Layer — Phase 4: MCP adapter + confirm loop.

Uses in-memory sqlite + a stub user; EHR transport faked where booking
touches it. Proves: contracts enforced pre-call, writes need confirmation,
confirms execute exactly once, denials record without side effects.
"""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app import models
from app.ai_assistant.mcp import adapter
from app.ai_assistant.nodes import tool_router
from app.db.base import Base


class U:
    def __init__(self, id=7, role="patient", hospital_id=None, patient_id=3, doctor_id=None):
        self.id = id; self.role = role; self.hospital_id = hospital_id
        self.patient_id = patient_id; self.doctor_id = doctor_id


def _db():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def _mk(db):
    h = models.Hospital(name="H", slug="hh", status="approved"); db.add(h); db.commit()
    p = models.Patient(full_name="Pat", email="p@x.org"); db.add(p); db.commit()
    d = models.Doctor(hospital_id=h.id, name="Dr T", status="active", duration_minutes=30); db.add(d); db.commit()
    c = models.Calendar(hospital_id=h.id, doctor_id=d.id, name="M", is_active=True, working_hours="{}"); db.add(c); db.commit()
    return h, p, d, c


def test_adapter_rejects_unknown_tool_without_calling():
    out = asyncio.run(adapter.call(_db(), "nope_tool", {}, user=U()))
    assert out["ok"] is False and out["code"] == "invalid"


def test_adapter_rejects_missing_args_without_calling():
    out = asyncio.run(adapter.call(_db(), "cancel_appointment", {}, user=U()))
    assert out["ok"] is False and out["code"] == "invalid"
    assert "appointment_id" in out["error"]


def test_adapter_denied_records_no_side_effect():
    db = _db(); h, p, d, c = _mk(db)
    s = datetime.now(timezone.utc) + timedelta(days=2)
    ap = models.Appointment(hospital_id=h.id, doctor_id=d.id, patient_id=999, calendar_id=c.id,
                            starts_at=s, ends_at=s + timedelta(minutes=30),
                            status="confirmed", idempotency_key="k9", correlation_id="c9")
    db.add(ap); db.commit()
    before = db.query(models.CapabilityExecution).count()
    out = asyncio.run(adapter.call(db, "cancel_appointment", {"appointment_id": ap.id}, user=U()))
    assert out["ok"] is False and out["code"] == "denied"
    assert db.query(models.Appointment).filter(models.Appointment.id == ap.id).first().status == "confirmed"
    assert db.query(models.CapabilityExecution).count() == before + 1


def test_adapter_read_success():
    db = _db(); h, p, d, c = _mk(db)
    out = asyncio.run(adapter.call(db, "search_doctors", {"specialty": ""}, user=U()))
    assert out["ok"] is True and out["code"] == "ok"
    assert any(x["name"] == "Dr T" for x in out["data"]["doctors"])


def test_write_needs_confirmation_no_call():
    async def go():
        return await tool_router.run({"intent": "cancel", "classification": {"intent": "cancel", "entities": {"appointment_id": 5}},
                                      "context_refs": {}, "trace": [], "_runtime": {}})
    out = asyncio.run(go())
    assert out["selected_tool"] == ""
    assert out["pending_confirmation"]["tool"] == "cancel_appointment"
    assert out["pending_confirmation"]["idempotency_key"]
    assert out["tool_status"] == "skipped"


def test_confirm_executes_exactly_once(monkeypatch):
    import app.services.booking as bk

    class FakeEHR:
        def __init__(self, *a, **k): pass
        async def cancel_appointment(self, ext_id): return {"id": ext_id, "status": "cancelled"}

    monkeypatch.setattr(bk, "EHRClient", FakeEHR)
    db = _db(); h, p, d, c = _mk(db)
    s = datetime.now(timezone.utc) + timedelta(days=2)
    ap = models.Appointment(hospital_id=h.id, doctor_id=d.id, patient_id=p.id, calendar_id=c.id,
                            starts_at=s, ends_at=s + timedelta(minutes=30),
                            status="confirmed", idempotency_key="kx", correlation_id="cx")
    db.add(ap); db.commit()
    me = U(patient_id=p.id)

    async def confirm_turn(pending, expect="confirmed"):
        from app.ai_assistant.nodes import tool_result
        st = {"intent": "confirm", "classification": {"intent": "confirm", "entities": {}},
              "context_refs": {}, "pending_confirmation": pending, "trace": [],
              "_runtime": {"db": db, "user": me, "conversation_id": 1, "corr": "c1"}}
        routed = await tool_router.run(st)
        assert routed["tool_status"] == expect, routed
        st.update(routed)
        return await tool_result.run(st)

    first = asyncio.run(confirm_turn({"tool": "cancel_appointment", "args": {"appointment_id": ap.id, "reason": "x"},
                                      "idempotency_key": "idem-1", "summary": "Cancel appointment."}))
    assert first["tool_result"]["ok"] is True
    assert first["pending_confirmation"] == {}
    assert db.query(models.Appointment).filter(models.Appointment.id == ap.id).first().status == "cancelled"

    # Second identical confirm: pending consumed → no second execution.
    second = asyncio.run(confirm_turn({}, expect="skipped"))
    assert second["tool_result"]["code"] == "skipped"


def test_decline_clears_pending():
    async def go():
        return await tool_router.run({"intent": "decline", "classification": {"intent": "decline", "entities": {}},
                                      "context_refs": {},
                                      "pending_confirmation": {"tool": "cancel_appointment", "args": {}},
                                      "trace": [], "_runtime": {}})
    out = asyncio.run(go())
    assert out["pending_confirmation"] == {}
    assert "won't change anything" in out["reply"]


def test_reschedule_missing_slot_asks_not_pending():
    async def go():
        return await tool_router.run({"intent": "reschedule",
                                      "classification": {"intent": "reschedule", "entities": {"appointment_id": 9}},
                                      "context_refs": {}, "trace": [], "_runtime": {}})
    out = asyncio.run(go())
    assert out["selected_tool"] == "" and not out.get("pending_confirmation", {}).get("tool")
    assert "date and time" in out["pending_clarification"]
