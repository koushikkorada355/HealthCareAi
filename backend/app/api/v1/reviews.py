"""Patient reviews of doctors/hospitals (completed visits only, one per appointment)."""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session
from ...db.session import get_db
from ...core.deps import get_current_user
from ... import models
from ...services.helpers import audit

router = APIRouter(tags=["reviews"])


def doctor_review_stats(db: Session, doctor_id: int) -> tuple[int, float]:
    n, avg = db.query(func.count(models.Review.id), func.avg(models.Review.rating)).filter(
        models.Review.doctor_id == doctor_id, models.Review.status == "approved").first() or (0, None)
    return int(n or 0), round(float(avg or 0), 2)


def hospital_review_stats(db: Session, hospital_id: int) -> tuple[int, float]:
    n, avg = db.query(func.count(models.Review.id), func.avg(models.Review.rating)).filter(
        models.Review.hospital_id == hospital_id, models.Review.status == "approved").first() or (0, None)
    return int(n or 0), round(float(avg or 0), 2)


class ReviewIn(BaseModel):
    appointment_id: int; target_type: str = "doctor"  # doctor|hospital
    rating: int = 5; title: str = ""; body: str = ""


@router.post("/reviews")
def create_r(b: ReviewIn, db: Session = Depends(get_db), u=Depends(get_current_user)):
    if u.role != "patient": raise HTTPException(403, "Only patients write reviews")
    if b.target_type not in ("doctor", "hospital"): raise HTTPException(400, "target_type must be doctor|hospital")
    if not (1 <= b.rating <= 5): raise HTTPException(400, "rating must be 1-5")
    ap = db.query(models.Appointment).filter(models.Appointment.id == b.appointment_id).first()
    if not ap: raise HTTPException(404, "Appointment not found")
    if ap.patient_id != u.patient_id: raise HTTPException(403, "Not your appointment")
    if ap.status != "completed": raise HTTPException(400, "Only completed visits can be reviewed")
    if db.query(models.Review).filter(models.Review.appointment_id == ap.id).first(): raise HTTPException(400, "This visit is already reviewed")
    r = models.Review(target_type=b.target_type, doctor_id=ap.doctor_id if b.target_type == "doctor" else None,
                      hospital_id=ap.hospital_id, appointment_id=ap.id, patient_id=ap.patient_id,
                      rating=b.rating, title=b.title[:255], body=b.body[:5000], status="approved")
    db.add(r); db.commit(); db.refresh(r)
    audit(db, "review.create", "review", r.id, ap.hospital_id, u.id, {"rating": b.rating}, ap.correlation_id)
    return {"id": r.id}


def _serialize(r, db):
    p = db.query(models.Patient).filter(models.Patient.id == r.patient_id).first()
    d = db.query(models.Doctor).filter(models.Doctor.id == r.doctor_id).first() if r.doctor_id else None
    return {"id": r.id, "target_type": r.target_type, "doctor_id": r.doctor_id, "doctor_name": d.name if d else "",
            "hospital_id": r.hospital_id, "appointment_id": r.appointment_id,
            "patient_name": p.full_name if p else "", "rating": r.rating, "title": r.title, "body": r.body,
            "status": r.status, "response_text": r.response_text,
            "created_at": r.created_at.isoformat() if r.created_at else None}


@router.get("/reviews")
def list_r(target_type: str = "", doctor_id: int | None = None, hospital_id: int | None = None,
           rating: int | None = None, status: str = "approved",
           db: Session = Depends(get_db), u=Depends(get_current_user)):
    q = db.query(models.Review)
    # Isolation: patients see own; hospital staff see own hospital; doctors see own rows.
    if u.role == "patient":
        q = q.filter(models.Review.patient_id == u.patient_id)
    elif u.role == "hospital_admin" and u.hospital_id:
        q = q.filter(models.Review.hospital_id == u.hospital_id)
    elif u.role == "doctor" and u.doctor_id:
        q = q.filter(models.Review.doctor_id == u.doctor_id)
    if target_type: q = q.filter(models.Review.target_type == target_type)
    if doctor_id: q = q.filter(models.Review.doctor_id == doctor_id)
    if hospital_id:
        if u.role == "hospital_admin" and u.hospital_id and int(hospital_id) != u.hospital_id: raise HTTPException(403, "Cross-tenant denied")
        q = q.filter(models.Review.hospital_id == int(hospital_id))
    if rating: q = q.filter(models.Review.rating == rating)
    if status and u.role == "patient":
        q = q.filter(models.Review.status == "approved")
    elif status:
        q = q.filter(models.Review.status == status)
    rows = q.order_by(models.Review.id.desc()).limit(200).all()
    return [_serialize(r, db) for r in rows]


@router.get("/reviews/summary")
def summary(doctor_id: int | None = None, hospital_id: int | None = None,
            db: Session = Depends(get_db), u=Depends(get_current_user)):
    if doctor_id:
        d = db.query(models.Doctor).filter(models.Doctor.id == doctor_id).first()
        if not d: raise HTTPException(404)
        if u.role == "hospital_admin" and u.hospital_id and d.hospital_id != u.hospital_id: raise HTTPException(403)
        n, avg = doctor_review_stats(db, doctor_id)
        dist = dict(db.query(models.Review.rating, func.count(models.Review.id)).filter(
            models.Review.doctor_id == doctor_id, models.Review.status == "approved").group_by(models.Review.rating).all())
        recent = db.query(models.Review).filter(models.Review.doctor_id == doctor_id, models.Review.status == "approved").order_by(models.Review.id.desc()).limit(5).all()
        return {"count": n, "avg": avg, "dist": {str(k): v for k, v in dist.items()}, "recent": [_serialize(r, db) for r in recent]}
    if hospital_id:
        if u.role == "hospital_admin" and u.hospital_id and int(hospital_id) != u.hospital_id: raise HTTPException(403)
        n, avg = hospital_review_stats(db, int(hospital_id))
        dist = dict(db.query(models.Review.rating, func.count(models.Review.id)).filter(
            models.Review.hospital_id == int(hospital_id), models.Review.status == "approved").group_by(models.Review.rating).all())
        recent = db.query(models.Review).filter(models.Review.hospital_id == int(hospital_id), models.Review.status == "approved").order_by(models.Review.id.desc()).limit(5).all()
        return {"count": n, "avg": avg, "dist": {str(k): v for k, v in dist.items()}, "recent": [_serialize(r, db) for r in recent]}
    raise HTTPException(400, "doctor_id or hospital_id is required")


@router.patch("/reviews/{rid}")
def patch_r(rid: int, body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    r = db.query(models.Review).filter(models.Review.id == rid).first()
    if not r: raise HTTPException(404)
    if u.role == "hospital_admin" and r.hospital_id != u.hospital_id: raise HTTPException(403)
    if u.role not in ("platform_admin", "hospital_admin"): raise HTTPException(403)
    if "status" in body:
        if body["status"] not in ("approved", "hidden"): raise HTTPException(400, "status must be approved|hidden")
        r.status = body["status"]
    if "response_text" in body:
        r.response_text = (body["response_text"] or "")[:2000]
        r.response_at = datetime.now(timezone.utc) if r.response_text else None
    db.commit()
    audit(db, "review.moderate", "review", rid, r.hospital_id, u.id, {"status": r.status}, "")
    return {"ok": True}
