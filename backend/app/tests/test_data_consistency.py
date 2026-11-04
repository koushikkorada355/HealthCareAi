"""End-to-end data consistency: DB is source of truth, AI never invents success.

Covers: create->read, update->read, delete->read, search correctness,
user isolation, failure accuracy, success accuracy, AI proof gate.
Uses SQLite in-memory (Postgres exclusion skipped, same as other suites).
"""
import asyncio
from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app import models


def _db():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def _mk(db):
    h = models.Hospital(name="H", slug="h-cons", status="approved")
    db.add(h); db.commit()
    d = models.Doctor(hospital_id=h.id, name="Dr C", status="active", duration_minutes=30)
    db.add(d); db.commit()
    c = models.Calendar(hospital_id=h.id, doctor_id=d.id, name="Main", is_active=True,
                        working_hours='{"mon":[["09:00","17:00"]],"tue":[["09:00","17:00"]],"wed":[["09:00","17:00"]],"thu":[["09:00","17:00"]],"fri":[["09:00","15:00"]]}')
    db.add(c); db.commit()
    p = models.Patient(full_name="Pat", email="p@c.org")
    db.add(p); db.commit()
    u = models.User(email="p@c.org", password_hash="x", role="patient",
                    full_name="Pat", patient_id=p.id)
    db.add(u); db.commit()
    from app.services.workflows import ensure_defaults
    ensure_defaults(db, h.id)
    return h, d, c, p, u


def _slot(days_ahead=2, hour=10):
    s = (datetime.now(timezone.utc) + timedelta(days=days_ahead)).replace(
        hour=hour, minute=0, second=0, microsecond=0)
    while s.weekday() > 4:
        s += timedelta(days=1)
    s = s.replace(hour=hour)
    return s, s + timedelta(minutes=30)


def _user(role="patient", patient_id=None, hospital_id=None, uid=1):
    class U: pass
    u = U()
    u.role = role; u.patient_id = patient_id; u.doctor_id = None
    u.hospital_id = hospital_id; u.id = uid
    return u


def test_create_persists_and_reads_back():
    import app.services.booking as bk
    db = _db(); h, d, c, p, u = _mk(db)
    s, e = _slot()
    out = asyncio.run(bk.book_appointment(
        db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id,
        starts_at=s, ends_at=e, calendar_id=c.id,
        reason="check", idempotency_key="cons-1", corr="c1"))
    assert out["status"] == "confirmed"
    row = db.query(models.Appointment).filter(
        models.Appointment.id == out["appointment_id"]).first()
    assert row is not None and row.status == "confirmed"
    hist = db.query(models.AppointmentHistory).filter(
        models.AppointmentHistory.appointment_id == row.id).all()
    assert len(hist) >= 2


def test_update_modifies_and_reads_back():
    import app.services.booking as bk
    from app.services import appointments_svc as svc
    db = _db(); h, d, c, p, u = _mk(db)
    s, e = _slot()
    out = asyncio.run(bk.book_appointment(
        db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id,
        starts_at=s, ends_at=e, calendar_id=c.id,
        reason="check", idempotency_key="cons-2", corr="c1"))
    ns = s + timedelta(hours=2); ne = e + timedelta(hours=2)
    r = asyncio.run(svc.reschedule(
        db, {"appointment_id": out["appointment_id"],
             "new_starts_at": ns.isoformat(), "new_ends_at": ne.isoformat()},
        user=_user(patient_id=p.id), corr="c2"))
    assert r["status"] == "rescheduled"
    row = db.query(models.Appointment).filter(
        models.Appointment.id == out["appointment_id"]).first()
    assert row.starts_at.replace(tzinfo=None) == ns.replace(tzinfo=None)
    assert db.query(models.AppointmentHistory).filter(
        models.AppointmentHistory.appointment_id == row.id,
        models.AppointmentHistory.to_status == "rescheduled").count() >= 1


def test_illegal_transition_rolls_back_without_phantom_write():
    import app.services.booking as bk
    db = _db(); h, d, c, p, u = _mk(db)
    s, e = _slot()
    out = asyncio.run(bk.book_appointment(
        db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id,
        starts_at=s, ends_at=e, calendar_id=c.id,
        reason="check", idempotency_key="cons-3", corr="c1"))
    from app.services.helpers import transition
    ap = db.query(models.Appointment).filter(
        models.Appointment.id == out["appointment_id"]).first()
    transition(db, ap, "completed", actor="user:1", note="done", corr="c2")
    before = ap.starts_at.isoformat()
    try:
        from app.services import appointments_svc as svc
        ns = s + timedelta(hours=3); ne = e + timedelta(hours=3)
        asyncio.run(svc.reschedule(
            db, {"appointment_id": ap.id, "new_starts_at": ns.isoformat(),
                 "new_ends_at": ne.isoformat()},
            user=_user(patient_id=p.id), corr="c3"))
        assert False, "completed -> rescheduled must fail"
    except ValueError:
        pass
    db.refresh(ap)
    assert ap.starts_at.replace(tzinfo=None) == datetime.fromisoformat(before).replace(tzinfo=None)
    assert ap.status == "completed"


def test_delete_deactivates_and_upcoming_excludes():
    import app.services.booking as bk
    from app.services import appointments_svc as svc
    db = _db(); h, d, c, p, u = _mk(db)
    s, e = _slot()
    out = asyncio.run(bk.book_appointment(
        db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id,
        starts_at=s, ends_at=e, calendar_id=c.id,
        reason="check", idempotency_key="cons-4", corr="c1"))
    r = asyncio.run(svc.cancel(db, {"appointment_id": out["appointment_id"]},
                               user=_user(patient_id=p.id), corr="c2"))
    assert r["status"] == "cancelled"
    row = db.query(models.Appointment).filter(
        models.Appointment.id == out["appointment_id"]).first()
    assert row.status == "cancelled"
    mine = svc.list_mine(db, {"upcoming": "true"}, user=_user(patient_id=p.id))
    assert all(a["id"] != row.id for a in mine["appointments"])


def test_failed_operation_returns_error_not_success():
    import app.services.booking as bk
    db = _db(); h, d, c, p, u = _mk(db)
    s, e = _slot()
    asyncio.run(bk.book_appointment(
        db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id,
        starts_at=s, ends_at=e, calendar_id=c.id,
        reason="a", idempotency_key="cons-5a", corr="c1"))
    try:
        asyncio.run(bk.book_appointment(
            db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id,
            starts_at=s, ends_at=e, calendar_id=c.id,
            reason="b", idempotency_key="cons-5b", corr="c2"))
        assert False, "double booking must fail"
    except ValueError as ex:
        assert "SLOT_TAKEN" in str(ex) or "not available" in str(ex).lower()


def test_ai_proof_gate_strict():
    from app.ai_assistant import orchestration as orch
    from app.ai_assistant.nodes.response import violations, _claims_success
    # Bare appointment_id without status is NOT proof.
    assert orch.is_proven_result("create_appointment", {"appointment_id": 5}) is False
    # Failed status is NOT proof.
    assert orch.is_proven_result("x", {"id": 5, "status": "failed"}) is False
    # Explicit verified flag wins both ways.
    assert orch.is_proven_result("x", {"appointment_id": 5, "verified": True}) is True
    assert orch.is_proven_result("x", {"appointment_id": 5, "verified": False}) is False
    # Proven booking passes.
    assert orch.is_proven_result(
        "create_appointment",
        {"appointment_id": 9, "status": "confirmed", "verified": True}) is True
    # Failed tool + success wording is a violation.
    assert violations("Booked! All set.", False, False,
                      data={"appointment_id": 9}) != []
    assert _claims_success("Your appointment has been successfully booked") is True
    assert _claims_success("Here are 3 open slots.") is False


def test_user_isolation_between_patients():
    import app.services.booking as bk
    from app.services import appointments_svc as svc
    db = _db(); h, d, c, p, u = _mk(db)
    p2 = models.Patient(full_name="Other", email="o@c.org")
    db.add(p2); db.commit()
    s, e = _slot()
    asyncio.run(bk.book_appointment(
        db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id,
        starts_at=s, ends_at=e, calendar_id=c.id,
        reason="mine", idempotency_key="cons-7", corr="c1"))
    mine = svc.list_mine(db, {}, user=_user(patient_id=p.id))
    other = svc.list_mine(db, {}, user=_user(patient_id=p2.id, uid=2))
    assert len(mine["appointments"]) == 1
    assert len(other["appointments"]) == 0
