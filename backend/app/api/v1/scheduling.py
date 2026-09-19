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
