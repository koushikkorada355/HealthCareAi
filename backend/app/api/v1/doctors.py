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
    consultation_types: list = ["in_person"]; duration_minutes: int = 30; photo_url: str = ""
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
    for d in query.limit(100).all():
        sp = db.query(models.Specialty).filter(models.Specialty.id==d.specialty_id).first() if d.specialty_id else None
        h = db.query(models.Hospital).filter(models.Hospital.id==d.hospital_id).first()
        out.append({"id":d.id,"name":d.name,"hospital_id":d.hospital_id,"hospital_name":h.name if h else "","specialty":sp.name if sp else "","specialty_id":d.specialty_id,"department_id":d.department_id,"qualifications":d.qualifications,"experience_years":d.experience_years,"languages":d.languages,"consultation_types":d.consultation_types,"duration_minutes":d.duration_minutes,"status":d.status,"photo_url":d.photo_url,"rating":d.rating,"external_provider_id":d.external_provider_id})
    return out

@router.post("/doctors")
def create_d(b: DocIn, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role=="hospital_admin" and u.hospital_id!=b.hospital_id: raise HTTPException(403)
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    h = db.query(models.Hospital).filter(models.Hospital.id==b.hospital_id).first()
    if not h or h.status!="approved": raise HTTPException(400, "Hospital must be approved")
    d = models.Doctor(hospital_id=b.hospital_id, name=b.name, specialty_id=b.specialty_id, department_id=b.department_id, qualifications=b.qualifications, experience_years=b.experience_years, languages=json.dumps(b.languages), consultation_types=json.dumps(b.consultation_types), duration_minutes=b.duration_minutes, photo_url=b.photo_url, status="active", external_provider_id=b.external_provider_id or f"ext-prov-{b.hospital_id}-{b.name[:4]}")
    db.add(d); db.commit(); db.refresh(d)
    cal = models.Calendar(hospital_id=b.hospital_id, doctor_id=d.id, name="Main", is_active=True, working_hours=json.dumps({"mon":[["09:00","17:00"]],"tue":[["09:00","17:00"]],"wed":[["09:00","17:00"]],"thu":[["09:00","17:00"]],"fri":[["09:00","15:00"]]}))
    db.add(cal); db.commit(); db.refresh(cal)
    for wd in range(5):
        db.add(models.AvailabilityRule(calendar_id=cal.id, weekday=wd, start_time="09:00", end_time="17:00" if wd<4 else "15:00", slot_minutes=b.duration_minutes))
    db.commit()
    if b.email and not db.query(models.User).filter(models.User.email==b.email).first():
        from ...core.security import hash_password
        db.add(models.User(email=b.email, password_hash=hash_password("password123"), role="doctor", full_name=b.name, hospital_id=b.hospital_id, doctor_id=d.id)); db.commit()
    audit(db, "doctor.create", "doctor", d.id, b.hospital_id, u.id, {"name": b.name}, "")
    from ...services.workflows import fire_event
    fire_event(db, "doctor.created", b.hospital_id, {"doctor_id": d.id}, "")
    return {"id": d.id, "calendar_id": cal.id}

@router.get("/doctors/{did}")
def get_d(did: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    d = db.query(models.Doctor).filter(models.Doctor.id==did).first()
    if not d: raise HTTPException(404)
    tenant_hospital_id(u, d.hospital_id if u.role!="platform_admin" else None)
    sp = db.query(models.Specialty).filter(models.Specialty.id==d.specialty_id).first() if d.specialty_id else None
    cals = [{"id":c.id,"name":c.name,"is_active":c.is_active,"working_hours":c.working_hours} for c in db.query(models.Calendar).filter(models.Calendar.doctor_id==did).all()]
    return {"id":d.id,"name":d.name,"hospital_id":d.hospital_id,"specialty":sp.name if sp else "","qualifications":d.qualifications,"experience_years":d.experience_years,"languages":d.languages,"consultation_types":d.consultation_types,"duration_minutes":d.duration_minutes,"status":d.status,"photo_url":d.photo_url,"rating":d.rating,"external_provider_id":d.external_provider_id,"calendars":cals}

@router.patch("/doctors/{did}")
def patch_d(did: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    d = db.query(models.Doctor).filter(models.Doctor.id==did).first()
    if not d: raise HTTPException(404)
    if u.role=="hospital_admin" and u.hospital_id!=d.hospital_id: raise HTTPException(403)
    if u.role=="doctor" and u.doctor_id!=did: raise HTTPException(403)
    if u.role not in ("platform_admin","hospital_admin","doctor"): raise HTTPException(403)
    for k in ("name","qualifications","experience_years","duration_minutes","status","photo_url","external_provider_id"):
        if k in body: setattr(d, k, body[k])
    for k in ("languages","consultation_types"):
        if k in body: setattr(d, k, json.dumps(body[k]))
    db.commit(); audit(db, "doctor.update", "doctor", did, d.hospital_id, u.id, body, "")
    return {"ok": True}
