"""Booking: direct confirm, idempotent create, slot conflict handling (no external system)."""
import asyncio
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app import models
import app.services.booking as bk


def _db():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()

def _mk(db):
    h = models.Hospital(name="H", slug="h2", status="approved"); db.add(h); db.commit()
    d = models.Doctor(hospital_id=h.id, name="Dr T", status="active", duration_minutes=30); db.add(d); db.commit()
    c = models.Calendar(hospital_id=h.id, doctor_id=d.id, working_hours="{}"); db.add(c); db.commit()
    p = models.Patient(full_name="Pat", email="p@x.org"); db.add(p); db.commit()
    u = models.User(email="p@x.org", password_hash="x", role="patient", full_name="Pat", patient_id=p.id); db.add(u); db.commit()
    from app.services.workflows import ensure_defaults
    ensure_defaults(db, h.id)
    return h, d, c, p

def test_book_confirm():
    db = _db(); h, d, c, p = _mk(db)
    s = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
    out = asyncio.run(bk.book_appointment(db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id, starts_at=s, ends_at=s + timedelta(minutes=30), calendar_id=c.id, reason="shoulder pain", idempotency_key="k1", corr="c1"))
    assert out["verified"] and out["status"] == "confirmed"
    # idempotent replay
    out2 = asyncio.run(bk.book_appointment(db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id, starts_at=s, ends_at=s + timedelta(minutes=30), calendar_id=c.id, idempotency_key="k1", corr="c1"))
    assert out2["deduplicated"]

def test_double_booking_blocked():
    db = _db(); h, d, c, p = _mk(db)
    s = (datetime.now(timezone.utc) + timedelta(days=3)).replace(hour=11, minute=0, second=0, microsecond=0)
    asyncio.run(bk.book_appointment(db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id, starts_at=s, ends_at=s + timedelta(minutes=30), calendar_id=c.id, idempotency_key="kA", corr="cA"))
    try:
        asyncio.run(bk.book_appointment(db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id, starts_at=s, ends_at=s + timedelta(minutes=30), calendar_id=c.id, idempotency_key="kB", corr="cB"))
        assert False, "should conflict"
    except ValueError as e:
        assert "SLOT_TAKEN" in str(e) or "not available" in str(e).lower()

def test_overlapping_booking_rejected_with_code():
    """Overlapping (not exact-start) second booking is rejected, no row kept."""
    db = _db(); h, d, c, p = _mk(db)
    s = (datetime.now(timezone.utc) + timedelta(days=3)).replace(hour=14, minute=0, second=0, microsecond=0)
    asyncio.run(bk.book_appointment(db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id, starts_at=s, ends_at=s + timedelta(minutes=30), calendar_id=c.id, idempotency_key="kC", corr="cC"))
    n_before = db.query(models.Appointment).count()
    try:
        asyncio.run(bk.book_appointment(db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id, starts_at=s + timedelta(minutes=15), ends_at=s + timedelta(minutes=45), calendar_id=c.id, idempotency_key="kD", corr="cD"))
        assert False, "overlap should be rejected"
    except ValueError as e:
        assert "SLOT_TAKEN" in str(e) or "not available" in str(e).lower()
    assert db.query(models.Appointment).count() == n_before, "loser must leave no row"
