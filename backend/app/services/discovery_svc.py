"""Discovery business logic: hospitals, doctors, taxonomy, slots.

Used by both REST (`api/v1/hospitals|doctors|scheduling`) and MCP tools.
No HTTP, no MCP — pure (db, args, user) functions raising
ValueError (→400/409) / PermissionError (→403).
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app import models
from app.services.guards import (
    jload, own_appointment, resolve_doctor_id, review_avg, scope_check,
    serialize_appointment, token_match, tokens,
)


async def search_hospitals(db, a, user=None):
    q = db.query(models.Hospital).filter(models.Hospital.status == "approved")
    if a.get("city"):
        for tok in tokens(a["city"]):
            q = q.filter(models.Hospital.city.ilike(f"%{tok}%"))
    if a.get("q"):
        from sqlalchemy import or_ as _or
        conds = []
        for tok in tokens(a["q"]):
            t = f"%{tok}%"
            conds.append(models.Hospital.name.ilike(t))
            conds.append(models.Hospital.city.ilike(t))
        if conds:
            q = q.filter(_or(*conds))
    try:
        min_r = float(a.get("min_rating", 0) or 0)
    except (TypeError, ValueError):
        min_r = 0
    sort = str(a.get("sort", "")).lower()
    out = []
    for h in q.limit(100).all():
        rc, ra = review_avg(db, hospital_id=h.id, target="hospital")
        if ra < min_r:
            continue
        dcnt = db.query(models.Doctor).filter(
            models.Doctor.hospital_id == h.id, models.Doctor.status == "active").count()
        out.append({"id": h.id, "name": h.name, "city": h.city, "address": h.address,
                    "doctor_count": dcnt, "avg_rating": ra, "review_count": rc})
    if sort == "top_rated":
        out.sort(key=lambda x: (x["avg_rating"], x["review_count"]), reverse=True)
    elif sort == "most_reviewed":
        out.sort(key=lambda x: (x["review_count"], x["avg_rating"]), reverse=True)
    return {"hospitals": out[:20]}


async def search_doctors(db, a, user=None):
    scope_check(user, a.get("hospital_id"))
    q = db.query(models.Doctor).filter(models.Doctor.status == "active")
    if a.get("hospital_id"):
        q = q.filter(models.Doctor.hospital_id == int(a["hospital_id"]))
    elif a.get("hospital"):
        from sqlalchemy import or_ as _orh
        hconds = [models.Hospital.name.ilike(f"%{tok}%") for tok in tokens(a["hospital"])]
        if hconds:
            hids = [h.id for h in db.query(models.Hospital).filter(_orh(*hconds)).all()]
            if hids:
                q = q.filter(models.Doctor.hospital_id.in_(hids))
    elif user and getattr(user, "role", "") in ("hospital_admin", "doctor") and getattr(user, "hospital_id", None):
        q = q.filter(models.Doctor.hospital_id == user.hospital_id)
    if a.get("exclude_hospital") or a.get("exclude_hospital_id"):
        xids = set()
        if a.get("exclude_hospital_id"):
            try:
                xids.add(int(a["exclude_hospital_id"]))
            except (TypeError, ValueError):
                pass
        if a.get("exclude_hospital"):
            from sqlalchemy import or_ as _orx
            xconds = []
            for tok in tokens(a["exclude_hospital"]):
                t = f"%{tok}%"
                xconds.append(models.Hospital.name.ilike(t))
                xconds.append(models.Hospital.city.ilike(t))
            if xconds:
                xids.update(h.id for h in db.query(models.Hospital).filter(_orx(*xconds)).all())
        if xids:
            q = q.filter(~models.Doctor.hospital_id.in_(xids))
    if a.get("specialty"):
        from sqlalchemy import or_ as _or2
        conds = [models.Specialty.name.ilike(f"%{tok}%") for tok in tokens(a["specialty"])]
        if conds:
            q = q.join(models.Specialty, models.Specialty.id == models.Doctor.specialty_id,
                       isouter=True).filter(_or2(*conds))
    if a.get("q"):
        from sqlalchemy import or_ as _or3
        toks = tokens(a["q"])
        if toks:
            hconds = []
            for tok in toks:
                t = f"%{tok}%"
                hconds.append(models.Hospital.name.ilike(t))
                hconds.append(models.Hospital.city.ilike(t))
            hids = [h.id for h in db.query(models.Hospital).filter(_or3(*hconds)).all()] if hconds else []
            if hids:
                q = q.filter(models.Doctor.hospital_id.in_(hids))
            else:
                dconds = []
                for tok in toks:
                    t = f"%{tok}%"
                    dconds.append(models.Doctor.name.ilike(t))
                if dconds:
                    q = q.filter(_or3(*dconds))
    try:
        min_r = float(a.get("min_rating", 0) or 0)
    except (TypeError, ValueError):
        min_r = 0
    sort = str(a.get("sort", "")).lower()
    out = []
    for d in q.limit(100).all():
        sp = db.query(models.Specialty).filter(models.Specialty.id == d.specialty_id).first() if d.specialty_id else None
        h = db.query(models.Hospital).filter(models.Hospital.id == d.hospital_id).first()
        rc, ra = review_avg(db, doctor_id=d.id)
        if ra < min_r:
            continue
        out.append({"id": d.id, "name": d.name, "hospital_id": d.hospital_id,
                    "hospital_name": h.name if h else "", "specialty": sp.name if sp else "",
                    "experience_years": d.experience_years, "avg_rating": ra,
                    "review_count": rc, "duration_minutes": d.duration_minutes})
    if sort == "top_rated":
        out.sort(key=lambda x: (x["avg_rating"], x["review_count"]), reverse=True)
    elif sort == "most_reviewed":
        out.sort(key=lambda x: (x["review_count"], x["avg_rating"]), reverse=True)
    elif sort == "most_experienced":
        out.sort(key=lambda x: (x["experience_years"] or 0), reverse=True)
    return {"doctors": out[:20]}


async def get_doctor_details(db, a, user=None):
    if not a.get("doctor_id"):
        raise ValueError("doctor_id is required")
    d = db.query(models.Doctor).filter(models.Doctor.id == int(a["doctor_id"])).first()
    if not d:
        raise ValueError("Doctor not found")
    scope_check(user, d.hospital_id)
    h = db.query(models.Hospital).filter(models.Hospital.id == d.hospital_id).first()
    rc, ra = review_avg(db, doctor_id=d.id)
    slots: list = []
    try:
        from app.scheduling.engine import compute_slots
        base = datetime.now(timezone.utc)
        for i in range(3):
            slots += compute_slots(db, d.id, base + timedelta(days=i), None)
            if len(slots) >= 5:
                break
        slots = slots[:5]
    except Exception:
        slots = []
    return {"id": d.id, "name": d.name, "hospital_name": h.name if h else "",
            "avg_rating": ra, "review_count": rc, "next_slots": slots}


async def get_hospital_details(db, a, user=None):
    if not a.get("hospital_id"):
        raise ValueError("hospital_id is required")
    h = db.query(models.Hospital).filter(models.Hospital.id == int(a["hospital_id"])).first()
    if not h:
        raise ValueError("Hospital not found")
    scope_check(user, h.id)
    rc, ra = review_avg(db, hospital_id=h.id, target="hospital")
    dcnt = db.query(models.Doctor).filter(
        models.Doctor.hospital_id == h.id, models.Doctor.status == "active").count()
    return {"id": h.id, "name": h.name, "city": h.city, "address": h.address,
            "avg_rating": ra, "review_count": rc, "doctor_count": dcnt}


async def get_hospital_info(db, a, user=None):
    hid = int(a["hospital_id"])
    h = db.query(models.Hospital).filter(models.Hospital.id == hid).first()
    if not h:
        raise ValueError("Hospital not found")
    scope_check(user, h.id)
    if user and getattr(user, "role", "") == "patient" and h.status != "approved":
        raise PermissionError("Hospital not available")
    rc, ra = review_avg(db, hospital_id=h.id, target="hospital")
    depts = [{"id": d.id, "name": d.name} for d in
             db.query(models.Department).filter(models.Department.hospital_id == hid).all()]
    specs = [{"id": s.id, "name": s.name} for s in
             db.query(models.Specialty).filter(
                 (models.Specialty.hospital_id == hid)
                 | (models.Specialty.hospital_id.is_(None))).all()]
    docs = db.query(models.Doctor).filter(
        models.Doctor.hospital_id == hid, models.Doctor.status == "active").limit(10).all()
    return {"id": h.id, "name": h.name, "city": h.city, "address": h.address,
            "phone": h.phone, "contact_email": h.contact_email,
            "operating_hours": jload(h.operating_hours, {}),
            "services": jload(h.services, []),
            "departments": depts, "specialties": specs,
            "doctor_count": len(docs),
            "doctors": [{"id": d.id, "name": d.name} for d in docs],
            "avg_rating": ra, "review_count": rc}


# kind: taxonomy_list — one executor for specialties/departments/types/questionnaires.
TAXONOMY = {
    "list_specialties": {"model": "Specialty", "allow_global": True},
    "list_departments": {"model": "Department", "allow_global": False},
    "list_appointment_types": {"model": "AppointmentType", "allow_global": True},
    "list_questionnaires": {"model": "Questionnaire", "allow_global": True,
                            "active_field": "is_active"},
}


async def taxonomy_list(db, a, tool: str, user=None):
    cfg = TAXONOMY[tool]
    model = getattr(models, cfg["model"])
    hid = a.get("hospital_id")
    if hid not in (None, ""):
        try:
            hid = int(hid)
        except (TypeError, ValueError):
            raise ValueError("hospital_id must be an integer")
        scope_check(user, hid)
        if cfg["model"] == "Specialty":
            q = db.query(model).filter(
                (model.hospital_id == hid) | (model.hospital_id.is_(None)))
        else:
            q = db.query(model).filter(model.hospital_id == hid)
    elif cfg.get("allow_global") is False:
        raise ValueError("hospital_id is required")
    else:
        q = db.query(model)
    if cfg.get("active_field"):
        q = q.filter(getattr(model, cfg["active_field"]).is_(True))
    rows = q.order_by(model.id).limit(100).all()
    key = {"Specialty": "specialties", "Department": "departments",
           "AppointmentType": "appointment_types",
           "Questionnaire": "questionnaires"}[cfg["model"]]
    out = []
    for r in rows:
        if cfg["model"] == "AppointmentType":
            out.append({"id": r.id, "hospital_id": r.hospital_id, "name": r.name,
                        "duration_minutes": r.duration_minutes,
                        "modes": jload(getattr(r, "modes", "[]"), [])})
        elif cfg["model"] == "Questionnaire":
            out.append({"id": r.id, "hospital_id": r.hospital_id, "title": r.title,
                        "category": r.category, "is_active": r.is_active})
        else:
            out.append({"id": r.id, "name": r.name,
                        "hospital_id": getattr(r, "hospital_id", None)})
    return {key: out}


async def check_availability(db, a, user=None):
    if not a.get("doctor_id") and a.get("doctor_name"):
        did = resolve_doctor_id(db, doctor_name=str(a.get("doctor_name", "")))
        if did:
            a = {**a, "doctor_id": did}
    if not a.get("doctor_id"):
        raise ValueError("doctor_id is required")
    from app.scheduling.engine import compute_slots
    did = int(a["doctor_id"])
    d = db.query(models.Doctor).filter(models.Doctor.id == did).first()
    if not d:
        raise ValueError("Doctor not found")
    scope_check(user, d.hospital_id)
    days = int(a.get("days", 7) or 7)
    days = max(1, min(days, 14))
    base = datetime.now(timezone.utc)
    if a.get("date"):
        try:
            base = datetime.fromisoformat(str(a["date"]).replace("Z", "+00:00"))
            if base.tzinfo is None:
                base = base.replace(tzinfo=timezone.utc)
        except ValueError:
            raise ValueError("date must be ISO-8601")
    out: list = []
    for i in range(days):
        out += compute_slots(db, did, base + timedelta(days=i), None)
        if len(out) >= 40:
            break
    part = str(a.get("day_part", "")).lower()
    if part in ("morning", "afternoon", "evening"):
        lo, hi = {"morning": (5, 12), "afternoon": (12, 17), "evening": (17, 22)}[part]
        filt = []
        for s in out:
            try:
                hr = datetime.fromisoformat(s["starts_at"]).hour
            except Exception:
                continue
            if lo <= hr < hi:
                filt.append(s)
        out = filt
    return {"doctor_id": did, "slots": out[:20], "day_part": part or "all"}


async def find_next_available(db, a, user=None):
    from app.scheduling.engine import compute_slots
    days = max(1, min(int(a.get("days", 7) or 7), 14))
    limit = max(1, min(int(a.get("limit", 10) or 10), 20))
    base = datetime.now(timezone.utc)
    if a.get("date"):
        try:
            base = datetime.fromisoformat(str(a["date"]).replace("Z", "+00:00"))
            if base.tzinfo is None:
                base = base.replace(tzinfo=timezone.utc)
        except ValueError:
            raise ValueError("date must be ISO-8601")
    q = db.query(models.Doctor).filter(models.Doctor.status == "active")
    if a.get("hospital_id") not in (None, ""):
        q = q.filter(models.Doctor.hospital_id == int(a["hospital_id"]))
    elif a.get("hospital"):
        toks = tokens(str(a["hospital"]))
        if toks:
            from sqlalchemy import or_ as _or
            conds = []
            for tok in toks:
                t = f"%{tok}%"
                conds.append(models.Hospital.name.ilike(t))
                conds.append(models.Hospital.city.ilike(t))
            hids = [h.id for h in db.query(models.Hospital).filter(_or(*conds)).all()]
            if hids:
                q = q.filter(models.Doctor.hospital_id.in_(hids))
    if a.get("specialty"):
        from sqlalchemy import or_ as _or2
        conds = [models.Specialty.name.ilike(f"%{tok}%") for tok in tokens(str(a["specialty"]))]
        if conds:
            q = q.join(models.Specialty,
                       models.Specialty.id == models.Doctor.specialty_id,
                       isouter=True).filter(_or2(*conds))
    if not a.get("specialty") and not a.get("hospital_id") and not a.get("hospital"):
        raise ValueError("specialty or hospital/hospital_id is required")
    part = str(a.get("day_part", "")).lower()
    pool: list = []
    for d in q.limit(10).all():
        scope_check(user, d.hospital_id)
        for i in range(days):
            try:
                pool += compute_slots(db, d.id, base + timedelta(days=i), None)
            except Exception:
                continue
            if len(pool) >= 60:
                break
        if len(pool) >= 60:
            break
    if part in ("morning", "afternoon", "evening"):
        lo, hi = {"morning": (5, 12), "afternoon": (12, 17), "evening": (17, 22)}[part]
        filt = []
        for s in pool:
            try:
                hr = datetime.fromisoformat(str(s["starts_at"]).replace("Z", "+00:00")).hour
            except Exception:
                continue
            if lo <= hr < hi:
                filt.append(s)
        pool = filt
    pool.sort(key=lambda s: str(s.get("starts_at", "")))
    return {"slots": pool[:limit], "count": len(pool[:limit]), "day_part": part or "all"}
