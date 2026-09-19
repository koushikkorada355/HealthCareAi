from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...core.deps import get_current_user, tenant_hospital_id
from ... import models
from ...services.helpers import audit, ops, notify
from ...services.workflows import ensure_defaults
import json

router = APIRouter(tags=["hospitals"])

class HospIn(BaseModel):
    name: str; address: str = ""; city: str = ""; phone: str = ""; contact_email: str = ""
    operating_hours: dict = {}; services: list = []; ehr_vendor: str = "mock"; ehr_config: dict = {}

@router.post("/hospitals/apply")
def apply(b: HospIn, db: Session = Depends(get_db), u=Depends(get_current_user)):
    slug = "".join(c.lower() if c.isalnum() else "-" for c in b.name)[:60].strip("-")
    if db.query(models.Hospital).filter(models.Hospital.slug==slug).first(): slug += "-2"
    # Auto-assign Unsplash cover on create — never ask admin for an image.
    from ...utils.photos import hospital_cover_for
    cover_url = hospital_cover_for(slug)
    h = models.Hospital(name=b.name, slug=slug, status="submitted", address=b.address, city=b.city, phone=b.phone, contact_email=b.contact_email, operating_hours=json.dumps(b.operating_hours), services=json.dumps(b.services), ehr_vendor=b.ehr_vendor, ehr_config=json.dumps(b.ehr_config), cover_url=cover_url, external_facility_id=f"ext-fac-{slug}")
    db.add(h); db.commit(); db.refresh(h)
    if u.role == "hospital_admin" and not u.hospital_id: u.hospital_id = h.id; db.commit()
    audit(db, "hospital.apply", "hospital", h.id, h.id, u.id, {"name": b.name}, "")
    ops(db, "hospital.submitted", f"{b.name} submitted", "info", h.id, "", {})
    return {"id": h.id, "slug": slug, "status": h.status, "cover_url": h.cover_url}

@router.get("/hospitals")
def list_h(db: Session = Depends(get_db), u=Depends(get_current_user), status: str = "", q: str = "", city: str = ""):
    query = db.query(models.Hospital)
    if u.role == "hospital_admin" and u.hospital_id: query = query.filter(models.Hospital.id==u.hospital_id)
    elif u.role == "patient": query = query.filter(models.Hospital.status=="approved")
    if status: query = query.filter(models.Hospital.status==status)
    if city: query = query.filter(models.Hospital.city.ilike(f"%{city}%"))
    if q: query = query.filter(models.Hospital.name.ilike(f"%{q}%"))
    return [{"id":h.id,"name":h.name,"slug":h.slug,"status":h.status,"city":h.city,"phone":h.phone,"contact_email":h.contact_email,"services":h.services,"ehr_vendor":h.ehr_vendor,"cover_url":h.cover_url,"review_notes":h.review_notes} for h in query.limit(100).all()]

@router.get("/hospitals/{hid}")
def get_h(hid: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    h = db.query(models.Hospital).filter(models.Hospital.id==hid).first()
    if not h: raise HTTPException(404)
    tenant_hospital_id(u, hid if u.role!="platform_admin" else None)
    if u.role=="patient" and h.status!="approved": raise HTTPException(403)
    return {"id":h.id,"name":h.name,"slug":h.slug,"status":h.status,"address":h.address,"city":h.city,"phone":h.phone,"contact_email":h.contact_email,"operating_hours":h.operating_hours,"services":h.services,"ehr_vendor":h.ehr_vendor,"ehr_config":h.ehr_config,"cover_url":h.cover_url,"review_notes":h.review_notes,"external_facility_id":h.external_facility_id}

@router.patch("/hospitals/{hid}")
def patch_h(hid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    h = db.query(models.Hospital).filter(models.Hospital.id==hid).first()
    if not h: raise HTTPException(404)
    if u.role=="hospital_admin" and u.hospital_id!=hid: raise HTTPException(403, "Cross-tenant denied")
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    for k in ("name","address","city","phone","contact_email","operating_hours","services","ehr_vendor","ehr_config"):
        if k in body: setattr(h, k, json.dumps(body[k]) if isinstance(body[k],(dict,list)) else body[k])
    db.commit()
    audit(db, "hospital.update", "hospital", hid, hid, u.id, body, "")
    return {"ok": True}

@router.post("/hospitals/{hid}/review")
def review(hid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role != "platform_admin": raise HTTPException(403)
    h = db.query(models.Hospital).filter(models.Hospital.id==hid).first()
    if not h: raise HTTPException(404)
    action = body.get("action"); note = body.get("note","")
    mapping = {"submit":"submitted","under_review":"under_review","approve":"approved","reject":"rejected","corrections":"corrections_requested","suspend":"suspended","reactivate":"approved"}
    if action not in mapping: raise HTTPException(400, "bad action")
    h.status = mapping[action]; h.review_notes = note; db.commit()
    if h.status=="approved":
        ensure_defaults(db, h.id)
        db.add(models.HealthcareConnection(hospital_id=h.id, vendor=h.ehr_vendor or "mock", base_url="http://mock-ehr:8001", status="active", config_json="{}")); db.commit()
        from ...services.workflows import fire_event
        fire_event(db, "hospital.approved", h.id, {"hospital_id": h.id}, "")
        admins = db.query(models.User).filter(models.User.hospital_id==h.id).all()
        for a in admins: notify(db, "application_status", "Hospital approved", f"{h.name} is approved.", a.id, h.id, "hospital", h.id)
    audit(db, f"hospital.{action}", "hospital", hid, hid, u.id, {"note":note}, "")
    return {"id": hid, "status": h.status}

@router.get("/hospitals/{hid}/departments")
def depts(hid: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    tenant_hospital_id(u, hid if u.role!="platform_admin" else None)
    return [{"id":d.id,"name":d.name,"description":d.description} for d in db.query(models.Department).filter(models.Department.hospital_id==hid).all()]

@router.post("/hospitals/{hid}/departments")
def add_dept(hid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role=="hospital_admin" and u.hospital_id!=hid: raise HTTPException(403)
    if u.role not in ("platform_admin","hospital_admin"): raise HTTPException(403)
    d = models.Department(hospital_id=hid, name=body["name"], description=body.get("description","")); db.add(d); db.commit(); db.refresh(d)
    audit(db, "department.create", "department", d.id, hid, u.id, body, ""); return {"id": d.id}

@router.get("/hospitals/{hid}/specialties")
def specs(hid: int, db: Session = Depends(get_db)):
    return [{"id":s.id,"name":s.name} for s in db.query(models.Specialty).filter((models.Specialty.hospital_id==hid)|(models.Specialty.hospital_id==None)).all()]

@router.post("/hospitals/{hid}/specialties")
def add_spec(hid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role=="hospital_admin" and u.hospital_id!=hid: raise HTTPException(403)
    s = models.Specialty(hospital_id=hid, name=body["name"]); db.add(s); db.commit(); db.refresh(s); return {"id": s.id}
