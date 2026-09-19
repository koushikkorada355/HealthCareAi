"""EHR + integration: mapping, idempotent create, verify-then-confirm, unknown-outcome recovery (mocked transport)."""
import asyncio, json
from datetime import datetime, timedelta, timezone
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.db.base import Base
from app import models
import app.services.booking as bk

FAKE = {}
class FakeEHR:
    def __init__(self, *a, **k): pass
    async def create_appointment(self, payload, key=""):
        if key in FAKE: return FAKE[key]
        rec = {"id": "ext-1", **payload}
        FAKE[key] = rec; return rec
    async def get_appointment(self, ext_id):
        for v in FAKE.values():
            if v.get("id") == ext_id: return v
        return None

def _db():
    e = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(e)
    return sessionmaker(bind=e)()

def _mk(db):
    h = models.Hospital(name="H", slug="h2", status="approved", external_facility_id="f1"); db.add(h); db.commit()
    d = models.Doctor(hospital_id=h.id, name="Dr T", status="active", duration_minutes=30, external_provider_id="p1"); db.add(d); db.commit()
    c = models.Calendar(hospital_id=h.id, doctor_id=d.id, working_hours="{}"); db.add(c); db.commit()
    p = models.Patient(full_name="Pat", email="p@x.org", external_patient_id="ep1"); db.add(p); db.commit()
    u = models.User(email="p@x.org", password_hash="x", role="patient", full_name="Pat", patient_id=p.id); db.add(u); db.commit()
    from app.services.workflows import ensure_defaults
    ensure_defaults(db, h.id)
    return h, d, c, p

def test_book_verify_sync(monkeypatch):
    monkeypatch.setattr(bk, "EHRClient", FakeEHR)
    db = _db(); h, d, c, p = _mk(db)
    s = (datetime.now(timezone.utc) + timedelta(days=2)).replace(hour=10, minute=0, second=0, microsecond=0)
    out = asyncio.run(bk.book_appointment(db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id, starts_at=s, ends_at=s + timedelta(minutes=30), calendar_id=c.id, reason="shoulder pain", idempotency_key="k1", corr="c1"))
    assert out["verified"] and out["status"] == "confirmed"
    # idempotent replay
    out2 = asyncio.run(bk.book_appointment(db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id, starts_at=s, ends_at=s + timedelta(minutes=30), calendar_id=c.id, idempotency_key="k1", corr="c1"))
    assert out2["deduplicated"]

def test_double_booking_blocked(monkeypatch):
    monkeypatch.setattr(bk, "EHRClient", FakeEHR)
    db = _db(); h, d, c, p = _mk(db)
    s = (datetime.now(timezone.utc) + timedelta(days=3)).replace(hour=11, minute=0, second=0, microsecond=0)
    asyncio.run(bk.book_appointment(db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id, starts_at=s, ends_at=s + timedelta(minutes=30), calendar_id=c.id, idempotency_key="kA", corr="cA"))
    try:
        asyncio.run(bk.book_appointment(db, hospital_id=h.id, doctor_id=d.id, patient_id=p.id, starts_at=s, ends_at=s + timedelta(minutes=30), calendar_id=c.id, idempotency_key="kB", corr="cB"))
        assert False, "should conflict"
    except ValueError as e:
        assert "not available" in str(e).lower() or "conflict" in str(e).lower()

def test_unknown_outcome_recovery_path():
    db = _db(); h, d, c, p = _mk(db)
    s = (datetime.now(timezone.utc) + timedelta(days=4)).replace(hour=15, minute=0, second=0, microsecond=0)
    a = models.Appointment(hospital_id=h.id, doctor_id=d.id, patient_id=p.id, calendar_id=c.id, starts_at=s, ends_at=s + timedelta(minutes=30), status="pending", idempotency_key="kx", correlation_id="cx", integration_status="pending")
    db.add(a); db.commit()
    op = models.IntegrationOperation(hospital_id=h.id, kind="create", ref_type="appointment", ref_id=a.id, status="unknown_outcome", idempotency_key="kx", correlation_id="cx")
    db.add(op); db.commit()
    # recovery with unreachable EHR -> opens reconciliation (no duplicate)
    out = asyncio.run(bk.recover_unknown_outcome(db, a.id, op.id, "cx"))
    assert out["appointment_id"] == a.id
    assert db.query(models.ReconciliationRecord).count() >= 1
