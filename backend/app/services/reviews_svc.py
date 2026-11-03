"""Review business logic shared by REST and MCP."""
from __future__ import annotations

from app import models
from app.services.guards import review_avg, scope_check, uid


def list_reviews(db, a, user=None):
    from sqlalchemy import func as _f
    q = db.query(models.Review).filter(models.Review.status == "approved")
    target = a.get("target", "doctor")
    if a.get("doctor_id"):
        q = q.filter(models.Review.doctor_id == int(a["doctor_id"]))
    if a.get("hospital_id"):
        scope_check(user, a["hospital_id"])
        q = q.filter(models.Review.hospital_id == int(a["hospital_id"]))
    if a.get("rating") not in (None, ""):
        try:
            q = q.filter(models.Review.rating == int(a["rating"]))
        except (TypeError, ValueError):
            raise ValueError("rating must be an integer 1-5")
    rows = q.order_by(models.Review.id.desc()).limit(10).all()
    n, avg = review_avg(db, doctor_id=a.get("doctor_id"),
                        hospital_id=a.get("hospital_id"),
                        target=target if not a.get("doctor_id") else "doctor")
    return {"count": n or len(rows), "avg": avg,
            "reviews": [{"rating": r.rating, "title": r.title, "body": r.body[:500]} for r in rows]}


def create_review(db, a, user=None, corr=""):
    if not user or getattr(user, "role", "") != "patient":
        raise PermissionError("Only patients write reviews")
    for k in ("appointment_id", "target_type", "rating"):
        if a.get(k) in (None, ""):
            raise ValueError(f"{k} is required")
    if str(a["target_type"]) not in ("doctor", "hospital"):
        raise ValueError("target_type must be doctor|hospital")
    try:
        rating = int(a["rating"])
    except (TypeError, ValueError):
        raise ValueError("rating must be an integer 1-5")
    if not 1 <= rating <= 5:
        raise ValueError("rating must be 1-5")
    ap = db.query(models.Appointment).filter(
        models.Appointment.id == int(a["appointment_id"])).first()
    if not ap:
        raise ValueError("Appointment not found")
    if ap.patient_id != user.patient_id:
        raise PermissionError("Not your appointment")
    if ap.status != "completed":
        raise ValueError("Only completed visits can be reviewed")
    if db.query(models.Review).filter(
            models.Review.appointment_id == ap.id,
            models.Review.target_type == str(a["target_type"])).first():
        raise ValueError(f"This visit already has a {a['target_type']} review")
    from app.services.helpers import audit as _audit
    r = models.Review(target_type=str(a["target_type"]),
                      doctor_id=ap.doctor_id if str(a["target_type"]) == "doctor" else None,
                      hospital_id=ap.hospital_id, appointment_id=ap.id,
                      patient_id=ap.patient_id, rating=rating,
                      title=str(a.get("title", ""))[:255],
                      body=str(a.get("body", ""))[:5000], status="approved")
    db.add(r)
    db.commit()
    db.refresh(r)
    _audit(db, "review.create", "review", r.id, ap.hospital_id, uid(user),
           {"rating": rating}, ap.correlation_id)
    return {"id": r.id, "rating": rating}
