"""Unit: availability, slot validation, state transitions, idempotency keys, reconciliation logic."""
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app import models
from app.scheduling.engine import compute_slots, is_slot_free, can_transition
import json

def _db():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()

def _mk(db):
    h = models.Hospital(name="H", slug="h", status="approved"); db.add(h); db.commit()
    sp = models.Specialty(hospital_id=h.id, name="Orthopedics"); db.add(sp); db.commit()
    d = models.Doctor(hospital_id=h.id, specialty_id=sp.id, name="Dr T", status="active", duration_minutes=30); db.add(d); db.commit()
    c = models.Calendar(hospital_id=h.id, doctor_id=d.id, name="M", is_active=True, working_hours=json.dumps({"mon":[["09:00","17:00"]],"tue":[["09:00","17:00"]],"wed":[["09:00","17:00"]],"thu":[["09:00","17:00"]],"fri":[["09:00","17:00"]]})); db.add(c); db.commit()
    for wd in range(5):
        db.add(models.AvailabilityRule(calendar_id=c.id, weekday=wd, start_time="09:00", end_time="12:00", slot_minutes=30))
    db.commit()
    return h, d, c

def test_slots_only_from_engine_and_blocked_respected():
    db = _db(); h, d, c = _mk(db)
    day = datetime.now(timezone.utc)
    # find next weekday
    while day.weekday() > 4: day += timedelta(days=1)
    frozen = day.replace(hour=0, minute=0, second=0, microsecond=0)
    slots = compute_slots(db, d.id, day, now=frozen)
    assert len(slots) == 6  # 09-12 half hours
    s0 = datetime.fromisoformat(slots[0]["starts_at"]); e0 = datetime.fromisoformat(slots[0]["ends_at"])
    db.add(models.BlockedSlot(calendar_id=c.id, starts_at=s0, ends_at=e0, reason="x")); db.commit()
    assert not is_slot_free(db, d.id, c.id, s0, e0, now=frozen)

def test_past_slots_never_listed_or_bookable():
    from app.scheduling.engine import validate_slot
    db = _db(); h, d, c = _mk(db)
    day = datetime.now(timezone.utc)
    while day.weekday() > 4: day += timedelta(days=1)
    frozen = day.replace(hour=15, minute=0, second=0, microsecond=0)
    slots = compute_slots(db, d.id, day, now=frozen)
    assert all(datetime.fromisoformat(s["ends_at"]) > frozen for s in slots)
    assert len(slots) < 6  # morning slots already passed
    past_end = day.replace(hour=9, minute=30, second=0, microsecond=0)
    past_start = day.replace(hour=9, minute=0, second=0, microsecond=0)
    try:
        validate_slot(db, d.id, c.id, past_start, past_end, now=frozen)
        assert False, "past slot must not validate"
    except ValueError as e:
        assert "past" in str(e).lower()

def test_leave_and_booking_conflict():
    db = _db(); h, d, c = _mk(db)
    day = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=9, minute=30, second=0, microsecond=0)
    while day.weekday() > 4: day += timedelta(days=1)
    e = day + timedelta(minutes=30)
    db.add(models.Leave(doctor_id=d.id, starts_at=day, ends_at=e)); db.commit()
    assert not is_slot_free(db, d.id, c.id, day, e, now=day.replace(hour=0, minute=0))

def test_state_machine():
    assert can_transition("requested", "pending")
    assert can_transition("pending", "confirmed")
    assert not can_transition("cancelled", "confirmed")
    assert can_transition("sync_pending", "reconciliation_required")

def test_inactive_doctor_no_slots():
    db = _db(); h, d, c = _mk(db)
    d.status = "suspended"; db.commit()
    assert compute_slots(db, d.id, datetime.now(timezone.utc)) == []
