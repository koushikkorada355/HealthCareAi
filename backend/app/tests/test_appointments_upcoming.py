"""Upcoming filter: terminal visits are history even when starts_at is future.

Regression test for the AI-cancel display bug: cancelling via AI chat sets
status=cancelled in DB, but GET /appointments?upcoming=true kept returning
the row because it filtered only on starts_at >= now.
"""
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app import models


def _db():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()


def _user(role="patient", patient_id=None, hospital_id=None):
    class U:
        pass
    u = U()
    u.role = role
    u.patient_id = patient_id
    u.doctor_id = None
    u.hospital_id = hospital_id
    u.id = 1
    return u


def _seed(db):
    h = models.Hospital(name="H", slug="hup", status="approved", external_facility_id="f1")
    db.add(h); db.commit()
    d = models.Doctor(hospital_id=h.id, name="Dr T", status="active", duration_minutes=30)
    db.add(d); db.commit()
    p = models.Patient(full_name="Pat", email="p@x.org")
    db.add(p); db.commit()
    return h, d, p


def _appt(db, h, d, p, status, delta_days):
    import uuid
    s = datetime.now(timezone.utc) + timedelta(days=delta_days)
    a = models.Appointment(hospital_id=h.id, doctor_id=d.id, patient_id=p.id,
                           starts_at=s, ends_at=s + timedelta(minutes=30),
                           status=status, idempotency_key=f"k-{uuid.uuid4().hex[:8]}")
    db.add(a); db.commit()
    return a


def test_upcoming_excludes_terminal_future_visits():
    from app.api.v1.appointments import list_a

    db = _db()
    h, d, p = _seed(db)
    live = _appt(db, h, d, p, "confirmed", 2)
    resched = _appt(db, h, d, p, "rescheduled", 3)
    cancelled = _appt(db, h, d, p, "cancelled", 2)  # AI-cancelled future visit
    done = _appt(db, h, d, p, "completed", 2)
    noshow = _appt(db, h, d, p, "no_show", 2)
    failed = _appt(db, h, d, p, "failed", 2)
    past = _appt(db, h, d, p, "confirmed", -2)

    out = list_a(db, _user(patient_id=p.id), upcoming=True)
    ids = {r["id"] for r in out}
    assert live.id in ids and resched.id in ids
    assert cancelled.id not in ids, "cancelled future visit must not show under Upcoming"
    assert done.id not in ids and noshow.id not in ids and failed.id not in ids
    assert past.id not in ids


def test_ai_cancel_disappears_from_upcoming():
    """End-to-end at service level: cancel then list upcoming."""
    from app.api.v1.appointments import list_a
    from app.services.helpers import transition

    db = _db()
    h, d, p = _seed(db)
    a = _appt(db, h, d, p, "confirmed", 2)
    assert a.id in {r["id"] for r in list_a(db, _user(patient_id=p.id), upcoming=True)}
    transition(db, a, "cancelled", actor="user:1", note="via AI", corr="t1")
    assert a.id not in {r["id"] for r in list_a(db, _user(patient_id=p.id), upcoming=True)}
    # ...but still visible in history
    assert a.id in {r["id"] for r in list_a(db, _user(patient_id=p.id))}
