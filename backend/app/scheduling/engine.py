"""Central scheduling source of truth. AI must never invent slots — all slots come from here."""
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from .. import models
import json

VALID_TRANSITIONS = {
    "requested": {"pending","cancelled","failed"},
    "pending": {"confirmed","cancelled","failed"},
    "sync_pending": {"confirmed","failed","reconciliation_required"},
    "confirmed": {"rescheduled","cancelled","completed","no_show","reconciliation_required"},
    "rescheduled": {"confirmed","cancelled","completed"},
    "reconciliation_required": {"confirmed","cancelled","failed"},
    "failed": {"requested"},
    "cancelled": set(), "completed": set(), "no_show": set(),
}
APPT_ALIASES = {"synchronization pending":"sync_pending","synchronization_pending":"sync_pending","no-show":"no_show","reconciliation required":"reconciliation_required"}

def norm_status(s: str) -> str:
    s = (s or "").strip().lower()
    return APPT_ALIASES.get(s, s)

def can_transition(frm: str, to: str) -> bool:
    return norm_status(to) in VALID_TRANSITIONS.get(norm_status(frm), set())

def _parse_wh(cal) -> dict:
    try: return json.loads(cal.working_hours or "{}")
    except Exception: return {}

def _rules_for(db: Session, calendar_id: int, weekday: int):
    return db.query(models.AvailabilityRule).filter(models.AvailabilityRule.calendar_id==calendar_id, models.AvailabilityRule.weekday==weekday, models.AvailabilityRule.is_active==True).all()

def _parse_hhmm(v: str):
    """Parse 'HH:MM' strictly; raises ValueError on malformed input."""
    h, m = str(v).split(":")
    h, m = int(h), int(m)
    if not (0 <= h <= 23 and 0 <= m <= 59):
        raise ValueError(f"bad time {v!r}")
    return h, m

def compute_slots(db: Session, doctor_id: int, day: datetime, duration: int | None = None, now: datetime | None = None):
    """Return list of {starts_at, ends_at, calendar_id} for a UTC day (date part used).

    Slots fully in the past (ends_at <= now) are never listed. `now` is
    injectable for deterministic tests; defaults to current UTC time.
    """
    now = now or datetime.now(timezone.utc)
    doc = db.query(models.Doctor).filter(models.Doctor.id==doctor_id).first()
    if not doc or doc.status != "active": return []
    cals = db.query(models.Calendar).filter(models.Calendar.doctor_id==doctor_id, models.Calendar.is_active==True).all()
    if not cals: return []
    out = []
    wd = day.weekday()
    day0 = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
    for cal in cals:
        rules = _rules_for(db, cal.id, wd)
        if not rules:
            wh = _parse_wh(cal)
            key = ["mon","tue","wed","thu","fri","sat","sun"][wd]
            for win in wh.get(key, []):
                rules.append(type("R", (), {"start_time": win[0], "end_time": win[1], "slot_minutes": duration or doc.duration_minutes})())
        for r in rules:
            sm = duration or getattr(r, "slot_minutes", 30)
            if not isinstance(sm, (int, float)) or sm <= 0:
                continue  # ignore invalid durations instead of looping forever
            try:
                sh, smin = _parse_hhmm(r.start_time)
                eh, emin = _parse_hhmm(r.end_time)
            except (ValueError, AttributeError):
                continue  # skip malformed rules instead of 500
            cur = day0.replace(hour=sh, minute=smin)
            end = day0.replace(hour=eh, minute=emin)
            if end <= cur:
                continue
            while cur + timedelta(minutes=sm) <= end:
                slot_end = cur + timedelta(minutes=sm)
                if slot_end > now and is_slot_free(db, doctor_id, cal.id, cur, slot_end, now=now):
                    out.append({"starts_at": cur.isoformat(), "ends_at": slot_end.isoformat(), "calendar_id": cal.id, "doctor_id": doctor_id})
                cur = slot_end
    return out

def is_slot_free(db: Session, doctor_id: int, calendar_id: int, starts_at: datetime, ends_at: datetime, ignore_appointment_id: int | None = None, now: datetime | None = None) -> bool:
    now = now or datetime.now(timezone.utc)
    if ends_at <= now: return False  # past slots are never bookable
    doc = db.query(models.Doctor).filter(models.Doctor.id==doctor_id).first()
    if not doc or doc.status != "active": return False
    cal = db.query(models.Calendar).filter(models.Calendar.id==calendar_id).first()
    if not cal or not cal.is_active: return False
    # blocked
    b = db.query(models.BlockedSlot).filter(models.BlockedSlot.calendar_id==calendar_id, models.BlockedSlot.starts_at < ends_at, models.BlockedSlot.ends_at > starts_at).first()
    if b: return False
    # leave
    lv = db.query(models.Leave).filter(models.Leave.doctor_id==doctor_id, models.Leave.starts_at < ends_at, models.Leave.ends_at > starts_at).first()
    if lv: return False
    # booked
    q = db.query(models.Appointment).filter(models.Appointment.doctor_id==doctor_id, models.Appointment.starts_at < ends_at, models.Appointment.ends_at > starts_at, models.Appointment.status.in_(["pending","confirmed","sync_pending","rescheduled","reconciliation_required"]))
    if ignore_appointment_id: q = q.filter(models.Appointment.id != ignore_appointment_id)
    if q.first(): return False
    # working hours check
    wd = starts_at.weekday()
    rules = _rules_for(db, calendar_id, wd)
    wh_ok = False
    if rules:
        for r in rules:
            try:
                sh, smin = _parse_hhmm(r.start_time)
                eh, emin = _parse_hhmm(r.end_time)
            except (ValueError, AttributeError):
                continue
            ws = starts_at.replace(hour=sh, minute=smin, second=0, microsecond=0)
            we = starts_at.replace(hour=eh, minute=emin, second=0, microsecond=0)
            if starts_at >= ws and ends_at <= we: wh_ok = True
    else:
        wh = _parse_wh(cal)
        key = ["mon","tue","wed","thu","fri","sat","sun"][wd]
        for win in wh.get(key, []):
            try:
                sh, smin = _parse_hhmm(win[0])
                eh, emin = _parse_hhmm(win[1])
            except (ValueError, AttributeError, IndexError, TypeError):
                continue
            ws = starts_at.replace(hour=sh, minute=smin, second=0, microsecond=0)
            we = starts_at.replace(hour=eh, minute=emin, second=0, microsecond=0)
            if starts_at >= ws and ends_at <= we: wh_ok = True
        if not wh.get(key): wh_ok = True  # no constraint defined -> allow if other checks pass
    return wh_ok

def validate_slot(db: Session, doctor_id: int, calendar_id: int, starts_at: datetime, ends_at: datetime, ignore_appointment_id=None, now: datetime | None = None):
    now = now or datetime.now(timezone.utc)
    if ends_at <= now:
        raise ValueError("Slot is in the past")
    if not is_slot_free(db, doctor_id, calendar_id, starts_at, ends_at, ignore_appointment_id, now=now):
        raise ValueError("Slot is not available (blocked/leave/booked/hours/inactive)")
    return True
