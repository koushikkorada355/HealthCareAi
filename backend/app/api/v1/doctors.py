from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...core.deps import get_current_user, tenant_hospital_id
from ... import models
from ...services.helpers import audit
import json

router = APIRouter(tags=["doctors"])

class DocIn(BaseModel):
    hospital_id: int; name: str; specialty_id: int | None = None; department_id: int | None = None
    qualifications: str = "MD"; experience_years: int = 5; languages: list = ["English"]
    consultation_types: list = ["in_person"]; duration_minutes: int = 30
    external_provider_id: str = ""; email: str = ""

@router.get("/doctors")
def list_d(db: Session = Depends(get_db), u=Depends(get_current_user), hospital_id: int | None = None, specialty: str = "", q: str = ""):
    query = db.query(models.Doctor)
    if u.role in ("hospital_admin","doctor") and u.hospital_id: query = query.filter(models.Doctor.hospital_id==u.hospital_id)
    elif hospital_id: query = query.filter(models.Doctor.hospital_id==hospital_id)
    if u.role == "patient": query = query.filter(models.Doctor.status=="active")
    if specialty:
        query = query.join(models.Specialty, models.Specialty.id==models.Doctor.specialty_id, isouter=True).filter(models.Specialty.name.ilike(f"%{specialty}%"))
    if q: query = query.filter(models.Doctor.name.ilike(f"%{q}%"))
    out = []
    from .reviews import doctor_review_stats
    for d in query.limit(100).all():
        sp = db.query(models.Specialty).filter(models.Specialty.id==d.specialty_id).first() if d.specialty_id else None
        h = db.query(models.Hospital).filter(models.Hospital.id==d.hospital_id).first()
        _rc, _ra = doctor_review_stats(db, d.id)
        out.append({"id":d.id,"name":d.name,"hospital_id":d.hospital_id,"hospital_name":h.name if h else "","hospital_city":h.city if h else "","specialty":sp.name if sp else "","specialty_id":d.specialty_id,"department_id":d.department_id,"qualifications":d.qualifications,"experience_years":d.experience_years,"languages":d.languages,"consultation_types":d.consultation_types,"duration_minutes":d.duration_minutes,"status":d.status,"photo_url":d.photo_url,"rating":d.rating,"review_count":_rc,"avg_rating":_ra,"external_provider_id":d.external_provider_id})
    return out

@router.post("/doctors")
def create_d(b: DocIn, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role=="hospital_admin" and u.hospital_id!=b.hospital_id: raise HTTPException(403)
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    h = db.query(models.Hospital).filter(models.Hospital.id==b.hospital_id).first()
    if not h or h.status!="approved": raise HTTPException(400, "Hospital must be approved")
    # Adopt-by-email: the doctor signed up alone with their own credentials;
    # the admin links that login here. No temp passwords are ever created.
    if not b.email: raise HTTPException(400, "Doctor login email is required (the doctor signs up first, then you add their email)")
    lu = db.query(models.User).filter(models.User.email==b.email).first()
    if not lu: raise HTTPException(404, "No account with that email — the doctor must register first")
    if lu.role != "doctor": raise HTTPException(400, "That account is not a doctor account")
    if lu.doctor_id or lu.hospital_id: raise HTTPException(400, "That doctor is already linked to a hospital")
    # Auto-assign Unsplash photo on create — never ask admin/doctor for an image.
    from ...utils.photos import doctor_photo_for
    photo_url = doctor_photo_for(f"{b.hospital_id}-{b.name}")
    d = models.Doctor(hospital_id=b.hospital_id, name=b.name, specialty_id=b.specialty_id, department_id=b.department_id, qualifications=b.qualifications, experience_years=b.experience_years, languages=json.dumps(b.languages), consultation_types=json.dumps(b.consultation_types), duration_minutes=b.duration_minutes, photo_url=photo_url, status="invited", external_provider_id=b.external_provider_id or f"ext-prov-{b.hospital_id}-{b.name[:4]}")
    db.add(d); db.commit(); db.refresh(d)
    lu.doctor_id = d.id; lu.hospital_id = b.hospital_id; db.commit()
    cal = models.Calendar(hospital_id=b.hospital_id, doctor_id=d.id, name="Main", is_active=True, working_hours=json.dumps({"mon":[["09:00","17:00"]],"tue":[["09:00","17:00"]],"wed":[["09:00","17:00"]],"thu":[["09:00","17:00"]],"fri":[["09:00","15:00"]]}))
    db.add(cal); db.commit(); db.refresh(cal)
    for wd in range(5):
        db.add(models.AvailabilityRule(calendar_id=cal.id, weekday=wd, start_time="09:00", end_time="17:00" if wd<4 else "15:00", slot_minutes=b.duration_minutes))
    db.commit()
    audit(db, "doctor.create", "doctor", d.id, b.hospital_id, u.id, {"name": b.name, "via": "adopt"}, "")
    from ...services.workflows import fire_event
    fire_event(db, "doctor.created", b.hospital_id, {"doctor_id": d.id}, "")
    # The doctor keeps their own credentials — nothing to hand over.
    return {"id": d.id, "calendar_id": cal.id, "photo_url": d.photo_url, "login_email": lu.email, "status": d.status}

@router.get("/doctors/{did}")
def get_d(did: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    from sqlalchemy import func as _func
    from datetime import datetime, timezone, timedelta
    d = db.query(models.Doctor).filter(models.Doctor.id==did).first()
    if not d: raise HTTPException(404)
    tenant_hospital_id(u, d.hospital_id if u.role!="platform_admin" else None)
    sp = db.query(models.Specialty).filter(models.Specialty.id==d.specialty_id).first() if d.specialty_id else None
    h = db.query(models.Hospital).filter(models.Hospital.id==d.hospital_id).first()
    cals = [{"id":c.id,"name":c.name,"is_active":c.is_active,"working_hours":c.working_hours} for c in db.query(models.Calendar).filter(models.Calendar.doctor_id==did).all()]
    completed_visits = db.query(_func.count(models.Appointment.id)).filter(models.Appointment.doctor_id==did, models.Appointment.status=="completed").scalar() or 0
    upcoming_count = db.query(_func.count(models.Appointment.id)).filter(models.Appointment.doctor_id==did, models.Appointment.starts_at>=datetime.now(timezone.utc), models.Appointment.status.in_(["pending","confirmed","rescheduled"])).scalar() or 0
    next_slots = []
    try:
        from ...scheduling.engine import compute_slots
        base = datetime.now(timezone.utc)
        for i in range(3):
            next_slots += compute_slots(db, did, base + timedelta(days=i), None)
            if len(next_slots) >= 3: break
        next_slots = next_slots[:3]
    except Exception:
        next_slots = []
    from .reviews import doctor_review_stats
    _rcount, _ravg = doctor_review_stats(db, did)
    return {"id":d.id,"name":d.name,"hospital_id":d.hospital_id,"hospital_name":h.name if h else "","hospital_city":h.city if h else "","specialty":sp.name if sp else "","qualifications":d.qualifications,"experience_years":d.experience_years,"languages":d.languages,"consultation_types":d.consultation_types,"duration_minutes":d.duration_minutes,"status":d.status,"photo_url":d.photo_url,"rating":d.rating,"review_count":_rcount,"avg_rating":_ravg,"completed_visits":completed_visits,"upcoming_count":upcoming_count,"next_slots":next_slots,"external_provider_id":d.external_provider_id,"calendars":cals}

@router.patch("/doctors/{did}")
def patch_d(did: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    d = db.query(models.Doctor).filter(models.Doctor.id==did).first()
    if not d: raise HTTPException(404)
    if u.role=="hospital_admin" and u.hospital_id!=d.hospital_id: raise HTTPException(403)
    if u.role=="doctor" and u.doctor_id!=did: raise HTTPException(403)
    if u.role not in ("platform_admin","hospital_admin","doctor"): raise HTTPException(403)
    if u.role == "doctor":
        # Doctors manage permitted profile info only. Hospital-controlled
        # fields (status, specialty, department, name, external ID) stay admin-only.
        allowed = {}
        for k in ("qualifications", "languages", "consultation_types"):
            if k in body: allowed[k] = body[k]
        for k in ("experience_years", "duration_minutes"):
            if k in body:
                try: allowed[k] = int(body[k])
                except (TypeError, ValueError): raise HTTPException(400, f"{k} must be a number")
        for k, v in allowed.items():
            setattr(d, k, json.dumps(v) if k in ("languages", "consultation_types") else v)
        db.commit(); audit(db, "doctor.update.self", "doctor", did, d.hospital_id, u.id, {"fields": sorted(allowed)}, "")
        return {"ok": True}
    for k in ("name","qualifications","experience_years","duration_minutes","status","external_provider_id"):
        if k in body: setattr(d, k, body[k])
    if "specialty_id" in body:
        sid = body["specialty_id"]
        if sid is not None:
            sp = db.query(models.Specialty).filter(models.Specialty.id==sid).first()
            if not sp: raise HTTPException(400, "Specialty not found")
            if sp.hospital_id not in (None, d.hospital_id): raise HTTPException(400, "Specialty belongs to another hospital")
        d.specialty_id = sid
    if "department_id" in body:
        did2 = body["department_id"]
        if did2 is not None and not db.query(models.Department).filter(models.Department.id==did2, models.Department.hospital_id==d.hospital_id).first():
            raise HTTPException(400, "Department belongs to another hospital")
        d.department_id = did2
    for k in ("languages","consultation_types"):
        if k in body: setattr(d, k, json.dumps(body[k]))
    db.commit(); audit(db, "doctor.update", "doctor", did, d.hospital_id, u.id, body, "")
    return {"ok": True}

@router.delete("/doctors/{did}")
def delete_d(did: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    """Soft delete: deactivate doctor + login. Blocked with upcoming appointments."""
    from datetime import datetime, timezone
    d = db.query(models.Doctor).filter(models.Doctor.id==did).first()
    if not d: raise HTTPException(404)
    if u.role=="hospital_admin" and u.hospital_id!=d.hospital_id: raise HTTPException(403)
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    up = db.query(models.Appointment).filter(models.Appointment.doctor_id==did, models.Appointment.starts_at>=datetime.now(timezone.utc), models.Appointment.status.in_(["pending","confirmed","rescheduled"])).count()
    if up: raise HTTPException(400, f"Doctor has {up} upcoming appointment(s); reschedule or cancel them first")
    d.status = "inactive"; db.commit()
    lu = db.query(models.User).filter(models.User.doctor_id==did).first()
    if lu: lu.is_active = False; db.commit()
    audit(db, "doctor.deactivate", "doctor", did, d.hospital_id, u.id, {"via": "delete"}, "")
    return {"ok": True, "status": "inactive"}

@router.post("/doctors/{did}/accept")
def accept_d(did: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    """Doctor accepts their hospital invite (doctor phase). invited -> active."""
    if u.role != "doctor": raise HTTPException(403, "Only the invited doctor can accept")
    if u.doctor_id != did: raise HTTPException(403, "Not your invite")
    d = db.query(models.Doctor).filter(models.Doctor.id==did).first()
    if not d: raise HTTPException(404)
    if d.status != "invited": raise HTTPException(400, f"Invite is already {d.status}")
    d.status = "active"; db.commit()
    audit(db, "doctor.accept", "doctor", did, d.hospital_id, u.id, {}, "")
    return {"ok": True, "status": "active"}

@router.post("/doctors/{did}/decline")
def decline_d(did: int, body: dict | None = None, db: Session = Depends(get_db), u=Depends(get_current_user)):
    """Doctor declines the invite: link dissolved, profile closed."""
    if u.role != "doctor": raise HTTPException(403, "Only the invited doctor can decline")
    if u.doctor_id != did: raise HTTPException(403, "Not your invite")
    d = db.query(models.Doctor).filter(models.Doctor.id==did).first()
    if not d: raise HTTPException(404)
    if d.status != "invited": raise HTTPException(400, f"Invite is already {d.status}")
    d.status = "inactive"; db.commit()
    u.doctor_id = None; u.hospital_id = None; db.commit()
    audit(db, "doctor.decline", "doctor", did, d.hospital_id, u.id, {"reason": (body or {}).get("reason", "")}, "")
    return {"ok": True, "status": "declined"}
