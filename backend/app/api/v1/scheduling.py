from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from datetime import datetime, timezone, timedelta
from ...db.session import get_db
from ...core.deps import get_current_user, tenant_hospital_id
from ... import models
from ...scheduling.engine import compute_slots
from ...services.helpers import audit

router = APIRouter(tags=["scheduling"])

@router.get("/availability")
def availability(doctor_id: int, days_ahead: int = 7, duration_minutes: int | None = None, db: Session = Depends(get_db), u=Depends(get_current_user)):
    days_ahead = max(1, min(days_ahead, 30))
    if duration_minutes is not None and duration_minutes <= 0:
        raise HTTPException(400, "duration_minutes must be positive")
    slots = []
    base = datetime.now(timezone.utc)
    for i in range(days_ahead):
        slots += compute_slots(db, doctor_id, base + timedelta(days=i), duration_minutes)
        if len(slots) >= 40: break
    return {"doctor_id": doctor_id, "slots": slots[:40], "count": len(slots[:40]), "source": "scheduling_engine"}

class CalIn(BaseModel):
    hospital_id: int; doctor_id: int; name: str = "Main"; working_hours: dict = {}; is_active: bool = True

@router.get("/calendars")
def cals(doctor_id: int | None = None, hospital_id: int | None = None, db: Session = Depends(get_db), u=Depends(get_current_user)):
    q = db.query(models.Calendar)
    if doctor_id: q = q.filter(models.Calendar.doctor_id==doctor_id)
    if hospital_id: q = q.filter(models.Calendar.hospital_id==hospital_id)
    if u.role in ("hospital_admin","doctor") and u.hospital_id: q = q.filter(models.Calendar.hospital_id==u.hospital_id)
    return [{"id":c.id,"doctor_id":c.doctor_id,"hospital_id":c.hospital_id,"name":c.name,"is_active":c.is_active,"working_hours":c.working_hours} for c in q.limit(100).all()]

@router.post("/calendars")
def create_cal(b: CalIn, db: Session = Depends(get_db), u=Depends(get_current_user)):
    import json
    if u.role not in ("platform_admin", "hospital_admin", "doctor"): raise HTTPException(403)
    if u.role=="hospital_admin" and u.hospital_id!=b.hospital_id: raise HTTPException(403)
    if u.role=="doctor" and u.hospital_id!=b.hospital_id: raise HTTPException(403)
    c = models.Calendar(hospital_id=b.hospital_id, doctor_id=b.doctor_id, name=b.name, is_active=b.is_active, working_hours=json.dumps(b.working_hours or {}))
    db.add(c); db.commit(); db.refresh(c); return {"id": c.id}

def _cal_scope(db, cal_id, u):
    c = db.query(models.Calendar).filter(models.Calendar.id==cal_id).first()
    if not c: raise HTTPException(404, "Calendar not found")
    if u.role in ("hospital_admin", "doctor") and u.hospital_id and c.hospital_id != u.hospital_id: raise HTTPException(403, "Cross-tenant denied")
    return c

@router.patch("/calendars/{cid}")
def patch_cal(cid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    import json
    c = _cal_scope(db, cid, u)
    if u.role not in ("platform_admin", "hospital_admin", "doctor"): raise HTTPException(403)
    if "name" in body: c.name = body["name"]
    if "is_active" in body: c.is_active = bool(body["is_active"])
    if "working_hours" in body: c.working_hours = json.dumps(body["working_hours"] or {})
    db.commit(); audit(db, "schedule.calendar.update", "calendar", cid, c.hospital_id, u.id, body, ""); return {"ok": True}

class RuleIn(BaseModel):
    calendar_id: int; weekday: int; start_time: str; end_time: str; slot_minutes: int = 30; is_active: bool = True

@router.get("/availability-rules")
def rules(calendar_id: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    _cal_scope(db, calendar_id, u)
    rs = db.query(models.AvailabilityRule).filter(models.AvailabilityRule.calendar_id==calendar_id).order_by(models.AvailabilityRule.weekday, models.AvailabilityRule.start_time).all()
    return [{"id":r.id,"calendar_id":r.calendar_id,"weekday":r.weekday,"start_time":r.start_time,"end_time":r.end_time,"slot_minutes":r.slot_minutes,"is_active":r.is_active} for r in rs]

@router.post("/availability-rules")
def create_rule(b: RuleIn, db: Session = Depends(get_db), u=Depends(get_current_user)):
    from ...scheduling.engine import _parse_hhmm
    if u.role not in ("platform_admin", "hospital_admin", "doctor"): raise HTTPException(403)
    c = _cal_scope(db, b.calendar_id, u)
    if not (0 <= b.weekday <= 6): raise HTTPException(400, "weekday must be 0-6")
    try: _parse_hhmm(b.start_time); _parse_hhmm(b.end_time)
    except (ValueError, AttributeError): raise HTTPException(400, "start_time/end_time must be HH:MM")
    if b.slot_minutes <= 0: raise HTTPException(400, "slot_minutes must be positive")
    r = models.AvailabilityRule(calendar_id=b.calendar_id, weekday=b.weekday, start_time=b.start_time, end_time=b.end_time, slot_minutes=b.slot_minutes, is_active=b.is_active)
    db.add(r); db.commit(); db.refresh(r)
    audit(db, "schedule.rule.create", "availability_rule", r.id, c.hospital_id, u.id, b.model_dump(), ""); return {"id": r.id}

@router.patch("/availability-rules/{rid}")
def patch_rule(rid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    r = db.query(models.AvailabilityRule).filter(models.AvailabilityRule.id==rid).first()
    if not r: raise HTTPException(404)
    c = _cal_scope(db, r.calendar_id, u)
    if u.role not in ("platform_admin", "hospital_admin", "doctor"): raise HTTPException(403)
    for k in ("weekday", "start_time", "end_time", "slot_minutes", "is_active"):
        if k in body: setattr(r, k, body[k])
    db.commit(); audit(db, "schedule.rule.update", "availability_rule", rid, c.hospital_id, u.id, body, ""); return {"ok": True}

@router.delete("/availability-rules/{rid}")
def del_rule(rid: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    r = db.query(models.AvailabilityRule).filter(models.AvailabilityRule.id==rid).first()
    if not r: raise HTTPException(404)
    c = _cal_scope(db, r.calendar_id, u)
    if u.role not in ("platform_admin", "hospital_admin", "doctor"): raise HTTPException(403)
    db.delete(r); db.commit(); audit(db, "schedule.rule.delete", "availability_rule", rid, c.hospital_id, u.id, {}, ""); return {"ok": True}

class LeaveIn(BaseModel):
    doctor_id: int; starts_at: str; ends_at: str; reason: str = "leave"

@router.get("/leaves")
def leaves(doctor_id: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    d = db.query(models.Doctor).filter(models.Doctor.id==doctor_id).first()
    if not d: raise HTTPException(404)
    if u.role in ("hospital_admin", "doctor") and u.hospital_id and d.hospital_id != u.hospital_id: raise HTTPException(403, "Cross-tenant denied")
    ls = db.query(models.Leave).filter(models.Leave.doctor_id==doctor_id).order_by(models.Leave.starts_at).limit(200).all()
    return [{"id":x.id,"doctor_id":x.doctor_id,"starts_at":x.starts_at.isoformat(),"ends_at":x.ends_at.isoformat(),"reason":x.reason} for x in ls]

@router.post("/leaves")
def create_leave(b: LeaveIn, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role not in ("platform_admin", "hospital_admin", "doctor"): raise HTTPException(403)
    d = db.query(models.Doctor).filter(models.Doctor.id==b.doctor_id).first()
    if not d: raise HTTPException(404)
    if u.role in ("hospital_admin", "doctor") and u.hospital_id and d.hospital_id != u.hospital_id: raise HTTPException(403, "Cross-tenant denied")
    try:
        s = datetime.fromisoformat(str(b.starts_at).replace("Z", "+00:00")); e = datetime.fromisoformat(str(b.ends_at).replace("Z", "+00:00"))
    except (ValueError, TypeError): raise HTTPException(400, "starts_at/ends_at must be ISO-8601 datetimes")
    if e <= s: raise HTTPException(400, "ends_at must be after starts_at")
    lv = models.Leave(doctor_id=b.doctor_id, starts_at=s, ends_at=e, reason=b.reason)
    db.add(lv); db.commit(); db.refresh(lv)
    audit(db, "schedule.leave.create", "leave", lv.id, d.hospital_id, u.id, b.model_dump(), ""); return {"id": lv.id}

@router.delete("/leaves/{lid}")
def del_leave(lid: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    lv = db.query(models.Leave).filter(models.Leave.id==lid).first()
    if not lv: raise HTTPException(404)
    d = db.query(models.Doctor).filter(models.Doctor.id==lv.doctor_id).first()
    if u.role in ("hospital_admin", "doctor") and u.hospital_id and d and d.hospital_id != u.hospital_id: raise HTTPException(403, "Cross-tenant denied")
    if u.role not in ("platform_admin", "hospital_admin", "doctor"): raise HTTPException(403)
    hid = d.hospital_id if d else None
    db.delete(lv); db.commit(); audit(db, "schedule.leave.delete", "leave", lid, hid, u.id, {}, ""); return {"ok": True}

@router.get("/appointment-types")
def atypes(hospital_id: int | None = None, db: Session = Depends(get_db), u=Depends(get_current_user)):
    q = db.query(models.AppointmentType)
    if hospital_id: q = q.filter(models.AppointmentType.hospital_id==hospital_id)
    return [{"id":a.id,"hospital_id":a.hospital_id,"name":a.name,"duration_minutes":a.duration_minutes,"modes":a.modes} for a in q.limit(100).all()]

@router.post("/appointment-types")
def create_at(body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    import json
    if u.role not in ("platform_admin", "hospital_admin"): raise HTTPException(403)
    if u.role=="hospital_admin" and u.hospital_id!=body.get("hospital_id"): raise HTTPException(403)
    a = models.AppointmentType(hospital_id=body["hospital_id"], name=body["name"], duration_minutes=body.get("duration_minutes",30), modes=json.dumps(body.get("modes",["in_person"])))
    db.add(a); db.commit(); db.refresh(a); return {"id": a.id}

@router.patch("/appointment-types/{aid}")
def patch_at(aid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    import json
    a = db.query(models.AppointmentType).filter(models.AppointmentType.id==aid).first()
    if not a: raise HTTPException(404)
    if u.role=="hospital_admin" and u.hospital_id!=a.hospital_id: raise HTTPException(403)
    if u.role not in ("platform_admin", "hospital_admin"): raise HTTPException(403)
    if "name" in body: a.name = body["name"]
    if "duration_minutes" in body:
        if int(body["duration_minutes"]) <= 0: raise HTTPException(400, "duration_minutes must be positive")
        a.duration_minutes = int(body["duration_minutes"])
    if "modes" in body: a.modes = json.dumps(body["modes"])
    if "is_active" in body: a.is_active = bool(body["is_active"])
    db.commit(); audit(db, "schedule.atype.update", "appointment_type", aid, a.hospital_id, u.id, body, ""); return {"ok": True}

@router.delete("/appointment-types/{aid}")
def del_at(aid: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    a = db.query(models.AppointmentType).filter(models.AppointmentType.id==aid).first()
    if not a: raise HTTPException(404)
    if u.role=="hospital_admin" and u.hospital_id!=a.hospital_id: raise HTTPException(403)
    if u.role not in ("platform_admin", "hospital_admin"): raise HTTPException(403)
    if db.query(models.Appointment).filter(models.Appointment.appointment_type_id==aid).first(): raise HTTPException(400, "Type is used by appointments; deactivate instead")
    db.delete(a); db.commit(); return {"ok": True}

@router.get("/blocked-slots")
def blocked(calendar_id: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    return [{"id":b.id,"starts_at":b.starts_at.isoformat(),"ends_at":b.ends_at.isoformat(),"reason":b.reason} for b in db.query(models.BlockedSlot).filter(models.BlockedSlot.calendar_id==calendar_id).order_by(models.BlockedSlot.starts_at).limit(200).all()]

@router.post("/blocked-slots")
def create_blocked(body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role not in ("platform_admin", "hospital_admin", "doctor"): raise HTTPException(403)
    if not body.get("calendar_id") or not body.get("starts_at") or not body.get("ends_at"):
        raise HTTPException(400, "calendar_id, starts_at and ends_at are required")
    try:
        b = models.BlockedSlot(calendar_id=body["calendar_id"], starts_at=datetime.fromisoformat(str(body["starts_at"]).replace("Z","+00:00")), ends_at=datetime.fromisoformat(str(body["ends_at"]).replace("Z","+00:00")), reason=body.get("reason","blocked"))
    except (ValueError, TypeError):
        raise HTTPException(400, "starts_at/ends_at must be ISO-8601 datetimes")
    if b.ends_at <= b.starts_at:
        raise HTTPException(400, "ends_at must be after starts_at")
    db.add(b); db.commit(); db.refresh(b)
    audit(db, "schedule.block", "blocked_slot", b.id, None, u.id, body, ""); return {"id": b.id}

@router.delete("/blocked-slots/{bid}")
def del_blocked(bid: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role not in ("platform_admin", "hospital_admin", "doctor"): raise HTTPException(403)
    b = db.query(models.BlockedSlot).filter(models.BlockedSlot.id==bid).first()
    if not b: raise HTTPException(404, "Blocked slot not found")
    db.delete(b); db.commit()
    return {"ok": True}
