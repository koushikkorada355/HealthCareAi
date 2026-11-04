"""Profile / dashboard / prefs / notifications logic shared by REST and MCP."""
from __future__ import annotations

import json as _j
from datetime import datetime, timezone

from app import models
from app.services.guards import uid


def get_my_profile(db, a=None, user=None):
    out = {"id": uid(user), "email": getattr(user, "email", ""),
           "role": getattr(user, "role", ""),
           "full_name": getattr(user, "full_name", "")}
    if user and getattr(user, "role", "") == "patient" and getattr(user, "patient_id", None):
        p = db.query(models.Patient).filter(
            models.Patient.id == user.patient_id).first()
        if p:
            out["patient"] = {"phone": p.phone, "dob": p.dob, "gender": p.gender,
                              "address": p.address}
    return out


def update_my_profile(db, a=None, user=None):
    from app.services.helpers import audit as _audit
    allowed = ("full_name", "phone", "dob", "gender", "address")
    touched = [k for k in allowed if k in a]
    if not touched:
        raise ValueError("nothing to update (full_name, phone, dob, gender, address)")
    if "full_name" in a:
        name = (a["full_name"] or "").strip()
        if not name:
            raise ValueError("full_name is required")
        user.full_name = name[:255]
    if user and getattr(user, "role", "") == "patient" and getattr(user, "patient_id", None):
        p = db.query(models.Patient).filter(
            models.Patient.id == user.patient_id).first()
        if p:
            if "full_name" in a:
                p.full_name = user.full_name
            for k in ("phone", "dob", "gender", "address"):
                if k in a:
                    setattr(p, k, (a[k] or "")[:2000 if k == "address" else 64])
    db.commit()
    _audit(db, "user.update.self", "user", uid(user), getattr(user, "hospital_id", None),
           uid(user), {"fields": sorted(touched)}, "")
    return {"ok": True, "updated": sorted(touched)}


def get_my_dashboard(db, a=None, user=None):
    if not user or getattr(user, "role", "") != "patient":
        raise PermissionError("Patient dashboard only")
    now = datetime.now(timezone.utc)
    up = db.query(models.Appointment).filter(
        models.Appointment.patient_id == user.patient_id,
        models.Appointment.starts_at >= now,
        ~models.Appointment.status.in_(("cancelled", "completed", "no_show", "failed"))
    ).order_by(models.Appointment.starts_at).first()
    total = db.query(models.Appointment).filter(
        models.Appointment.patient_id == user.patient_id).count()
    due = db.query(models.QuestionnaireResponse).filter(
        models.QuestionnaireResponse.patient_id == user.patient_id,
        models.QuestionnaireResponse.status != "completed").count()
    item = None
    if up:
        item = {"id": up.id, "starts_at": up.starts_at.isoformat(),
                "status": up.status, "doctor_id": up.doctor_id}
    return {"upcoming": item, "total": total, "questionnaires_due": due}


def get_notifications(db, a, user=None):
    q = db.query(models.Notification).filter(
        models.Notification.user_id == uid(user))
    if str(a.get("unread_only", "")).lower() in ("1", "true", "yes"):
        q = q.filter(models.Notification.status != "read")
    rows = q.order_by(models.Notification.id.desc()).limit(20).all()
    return {"notifications": [
        {"id": n.id, "title": n.title, "body": n.body, "status": n.status} for n in rows]}


def get_prefs(db, user=None):
    row = db.query(models.UserContextPref).filter(
        models.UserContextPref.user_id == uid(user)).first()
    return {"prefs": _j.loads(row.prefs) if row and row.prefs else {}}


def update_prefs(db, a, user=None):
    pref = db.query(models.UserContextPref).filter(
        models.UserContextPref.user_id == uid(user)).first()
    if not pref:
        pref = models.UserContextPref(user_id=uid(user), prefs="{}")
        db.add(pref)
    try:
        cur = _j.loads(pref.prefs or "{}")
    except Exception:
        raise ValueError("Stored preferences are corrupt; reset required before update")
    cur.update(a.get("prefs", {}))
    pref.prefs = _j.dumps(cur)
    db.commit()
    return {"prefs": cur}


def list_my_questionnaires(db, a, user=None):
    pid = getattr(user, "patient_id", None) if user and getattr(user, "role", "") == "patient" else a.get("patient_id")
    if not pid and user and getattr(user, "role", "") in ("hospital_admin", "doctor"):
        return {"questionnaires": [], "note": "staff scope: pass patient_id"}
    if not pid:
        raise ValueError("patient_id is required")
    rows = (db.query(models.QuestionnaireResponse, models.Questionnaire)
            .join(models.Questionnaire,
                  models.Questionnaire.id == models.QuestionnaireResponse.questionnaire_id)
            .filter(models.QuestionnaireResponse.patient_id == int(pid),
                    models.QuestionnaireResponse.status != "completed")
            .order_by(models.QuestionnaireResponse.id.desc()).limit(20).all())
    return {"questionnaires": [
        {"response_id": r.id, "questionnaire_id": q.id, "title": q.title,
         "status": r.status, "appointment_id": r.appointment_id} for r, q in rows]}
