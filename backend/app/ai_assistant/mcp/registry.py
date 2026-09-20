"""MCP capability registry: typed, validated, authorized, idempotent, audited.

AI calls these — never DB/EHR directly. Every invoke writes a
CapabilityExecution row with correlation + idempotency key.
"""
from __future__ import annotations

import json
import time
import uuid
from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app import models

CAPABILITIES = [
    {"name": "search_hospitals", "description": "Search approved hospitals (q, city, min_rating, sort=top_rated|most_reviewed)", "idempotent": True},
    {"name": "search_doctors", "description": "Search active doctors globally (specialty, hospital name, hospital_id, q, min_rating, sort; exclude_hospital excludes a hospital by name). Omit filters for overall lists.", "idempotent": True},
    {"name": "get_doctor_details", "description": "Full doctor profile + review stats + next slots", "idempotent": True},
    {"name": "get_hospital_details", "description": "Full hospital profile + doctor count + review stats", "idempotent": True},
    {"name": "check_availability", "description": "Real slots from scheduling engine (doctor_id, date ISO, days 1-14, day_part=morning|afternoon|evening)", "idempotent": True},
    {"name": "lookup_patient", "description": "Patient lookup by name (own record for patients)", "idempotent": True},
    {"name": "get_appointment", "description": "Get appointment by id (ownership enforced)", "idempotent": True},
    {"name": "create_appointment", "description": "Book with verify+sync (hospital_id, doctor_id, patient_id, starts_at, ends_at)", "idempotent": True},
    {"name": "reschedule_appointment", "description": "Reschedule with revalidation", "idempotent": True},
    {"name": "cancel_appointment", "description": "Cancel + EHR cancel", "idempotent": True},
    {"name": "get_questionnaire", "description": "Get questionnaire + caller status", "idempotent": True},
    {"name": "submit_questionnaire", "description": "Submit structured answers (response_id, answers)", "idempotent": False},
    {"name": "send_notification", "description": "Queue notification (title, body)", "idempotent": False},
    {"name": "start_workflow", "description": "Trigger workflow event", "idempotent": False},
    {"name": "get_context", "description": "Get conversation context slices", "idempotent": True},
    {"name": "update_preferences", "description": "Update caller prefs", "idempotent": False},
    {"name": "verify_external_appointment", "description": "Re-read EHR record for appointment", "idempotent": True},
    {"name": "synchronize_state", "description": "Probe by idempotency key; sync safely, never duplicate", "idempotent": True},
    {"name": "transfer_to_human", "description": "Log a tracked request for the care team (returns reference id, visible on ops dashboards). No live agent exists.", "idempotent": False},
    {"name": "get_reviews", "description": "Approved reviews for doctor/hospital + avg", "idempotent": True},
    {"name": "list_my_appointments", "description": "Caller's own appointments (role-scoped)", "idempotent": True},
    {"name": "list_my_questionnaires", "description": "Caller's pending/due questionnaires with appointment links", "idempotent": True},
    {"name": "get_notifications", "description": "Caller's notification inbox", "idempotent": True},
]


def _audit(db, conv_id, name, status, inp, out, err, user_id, idem, corr, ms):
    try:
        db.add(models.CapabilityExecution(
            conversation_id=conv_id, name=name, status=status,
            input_json=json.dumps(inp)[:4000],
            output_json=json.dumps(out)[:4000] if out else "",
            error=(err or "")[:2000], actor_user_id=user_id,
            idempotency_key=idem or "", correlation_id=corr, latency_ms=ms))
        db.commit()
    except Exception:
        db.rollback()


def _uid(user) -> int | None:
    return getattr(user, "id", None)


def _scope_check(user, hospital_id=None):
    if (user and getattr(user, "role", "") in ("hospital_admin", "doctor")
            and hospital_id and getattr(user, "hospital_id", None)
            and int(hospital_id) != int(user.hospital_id)):
        raise PermissionError("Cross-tenant denied")


def _review_avg(db, doctor_id=None, hospital_id=None, target="doctor"):
    from sqlalchemy import func as _f
    q = db.query(_f.count(models.Review.id), _f.avg(models.Review.rating)).filter(
        models.Review.status == "approved")
    if target == "doctor" and doctor_id:
        q = q.filter(models.Review.doctor_id == doctor_id)
    elif hospital_id:
        q = q.filter(models.Review.hospital_id == hospital_id)
    n, avg = q.first() or (0, None)
    return int(n or 0), round(float(avg or 0), 2)


async def invoke(db: Session, name: str, args: dict, *, user, conversation_id=None,
                 idempotency_key="", corr="") -> dict:
    t0 = time.time()
    corr = corr or uuid.uuid4().hex[:12]
    idem = idempotency_key or (args or {}).get("idempotency_key", "")
    fn = _IMPL.get(name)
    if fn is None:
        _audit(db, conversation_id, name, "failed", args, None, "unknown capability",
               _uid(user), idem, corr, 0)
        raise ValueError(f"Unknown capability {name}")
    try:
        out = await fn(db, args or {}, user=user, corr=corr, idem=idem,
                       conversation_id=conversation_id)
        _audit(db, conversation_id, name, "success", args, out, "", _uid(user),
               idem, corr, int((time.time() - t0) * 1000))
        return {"ok": True, "capability": name, "correlation_id": corr, "data": out}
    except PermissionError as e:
        _audit(db, conversation_id, name, "denied", args, None, str(e), _uid(user),
               idem, corr, int((time.time() - t0) * 1000))
        raise
    except Exception as e:
        _audit(db, conversation_id, name, "failed", args, None, str(e), _uid(user),
               idem, corr, int((time.time() - t0) * 1000))
        raise


# ---- implementations (read-first, writes delegate to services) ----

async def _search_hospitals(db, a, user=None, corr="", idem="", conversation_id=None):
    q = db.query(models.Hospital).filter(models.Hospital.status == "approved")
    if a.get("city"):
        q = q.filter(models.Hospital.city.ilike(f"%{a['city']}%"))
    if a.get("q"):
        t = f"%{a['q']}%"
        q = q.filter((models.Hospital.name.ilike(t)) | (models.Hospital.city.ilike(t)))
    try:
        min_r = float(a.get("min_rating", 0) or 0)
    except (TypeError, ValueError):
        min_r = 0
    sort = str(a.get("sort", "")).lower()
    if sort not in ("", "top_rated", "most_reviewed"):
        raise ValueError("sort must be top_rated|most_reviewed")
    out = []
    for h in q.limit(100).all():
        rc, ra = _review_avg(db, hospital_id=h.id, target="hospital")
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


async def _search_doctors(db, a, user=None, corr="", idem="", conversation_id=None):
    _scope_check(user, a.get("hospital_id"))
    q = db.query(models.Doctor).filter(models.Doctor.status == "active")
    if a.get("hospital_id"):
        q = q.filter(models.Doctor.hospital_id == int(a["hospital_id"]))
    elif a.get("hospital"):
        # Hospital name -> id (global resolution, no hardcoded ids).
        t = f"%{a['hospital']}%"
        hids = [h.id for h in db.query(models.Hospital).filter(
            models.Hospital.name.ilike(t)).all()]
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
            t = f"%{a['exclude_hospital']}%"
            xids.update(h.id for h in db.query(models.Hospital).filter(
                (models.Hospital.name.ilike(t)) | (models.Hospital.city.ilike(t))).all())
        if xids:
            q = q.filter(~models.Doctor.hospital_id.in_(xids))
    if a.get("specialty"):
        q = q.join(models.Specialty, models.Specialty.id == models.Doctor.specialty_id,
                   isouter=True).filter(models.Specialty.name.ilike(f"%{a['specialty']}%"))
    if a.get("q"):
        # Hospital/city words belong to hospitals, not doctor names: if the
        # query matches a hospital name/city, scope to those hospitals.
        t = f"%{a['q']}%"
        hids = [h.id for h in db.query(models.Hospital).filter(
            (models.Hospital.name.ilike(t)) | (models.Hospital.city.ilike(t))).all()]
        if hids:
            q = q.filter(models.Doctor.hospital_id.in_(hids))
        else:
            q = q.filter(models.Doctor.name.ilike(t))
    try:
        min_r = float(a.get("min_rating", 0) or 0)
    except (TypeError, ValueError):
        min_r = 0
    sort = str(a.get("sort", "")).lower()
    if sort not in ("", "top_rated", "most_reviewed", "most_experienced"):
        raise ValueError("sort must be top_rated|most_reviewed|most_experienced")
    out = []
    for d in q.limit(100).all():
        sp = db.query(models.Specialty).filter(models.Specialty.id == d.specialty_id).first() if d.specialty_id else None
        h = db.query(models.Hospital).filter(models.Hospital.id == d.hospital_id).first()
        rc, ra = _review_avg(db, doctor_id=d.id)
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


async def _get_doctor_details(db, a, user=None, corr="", idem="", conversation_id=None):
    if not a.get("doctor_id"):
        raise ValueError("doctor_id is required")
    d = db.query(models.Doctor).filter(models.Doctor.id == int(a["doctor_id"])).first()
    if not d:
        raise ValueError("Doctor not found")
    _scope_check(user, d.hospital_id)
    h = db.query(models.Hospital).filter(models.Hospital.id == d.hospital_id).first()
    rc, ra = _review_avg(db, doctor_id=d.id)
    slots: list = []
    try:
        from app.scheduling.engine import compute_slots
        base = datetime.now(timezone.utc)
        from datetime import timedelta
        for i in range(3):
            slots += compute_slots(db, d.id, base + timedelta(days=i), None)
            if len(slots) >= 5:
                break
        slots = slots[:5]
    except Exception:
        slots = []
    return {"id": d.id, "name": d.name, "hospital_name": h.name if h else "",
            "avg_rating": ra, "review_count": rc, "next_slots": slots}


async def _get_hospital_details(db, a, user=None, corr="", idem="", conversation_id=None):
    if not a.get("hospital_id"):
        raise ValueError("hospital_id is required")
    h = db.query(models.Hospital).filter(models.Hospital.id == int(a["hospital_id"])).first()
    if not h:
        raise ValueError("Hospital not found")
    _scope_check(user, h.id)
    rc, ra = _review_avg(db, hospital_id=h.id, target="hospital")
    dcnt = db.query(models.Doctor).filter(
        models.Doctor.hospital_id == h.id, models.Doctor.status == "active").count()
    return {"id": h.id, "name": h.name, "city": h.city, "address": h.address,
            "avg_rating": ra, "review_count": rc, "doctor_count": dcnt}


async def _check_availability(db, a, user=None, corr="", idem="", conversation_id=None):
    if not a.get("doctor_id"):
        raise ValueError("doctor_id is required")
    from datetime import timedelta
    from app.scheduling.engine import compute_slots
    did = int(a["doctor_id"])
    d = db.query(models.Doctor).filter(models.Doctor.id == did).first()
    if not d:
        raise ValueError("Doctor not found")
    _scope_check(user, d.hospital_id)
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


async def _lookup_patient(db, a, user=None, corr="", idem="", conversation_id=None):
    if user and getattr(user, "role", "") == "patient":
        p = db.query(models.Patient).filter(models.Patient.id == user.patient_id).first()
        return {"id": p.id, "full_name": p.full_name} if p else {}
    q = str(a.get("q", ""))
    rows = db.query(models.Patient).filter(models.Patient.full_name.ilike(f"%{q}%")).limit(10).all() if q else []
    return {"patients": [{"id": p.id, "full_name": p.full_name} for p in rows]}


def _serialize_appt(db, a):
    d = db.query(models.Doctor).filter(models.Doctor.id == a.doctor_id).first()
    h = db.query(models.Hospital).filter(models.Hospital.id == a.hospital_id).first()
    return {"id": a.id, "status": a.status, "starts_at": a.starts_at.isoformat(),
            "ends_at": a.ends_at.isoformat(), "mode": a.mode,
            "doctor_id": a.doctor_id, "doctor_name": d.name if d else "",
            "hospital_id": a.hospital_id, "hospital_name": h.name if h else "",
            "external_id": a.external_appointment_id,
            "integration_status": a.integration_status, "correlation_id": a.correlation_id}


def _own_appt(db, aid, user):
    a = db.query(models.Appointment).filter(models.Appointment.id == int(aid)).first()
    if not a:
        raise ValueError("Appointment not found")
    if user and getattr(user, "role", "") == "patient" and a.patient_id != user.patient_id:
        raise PermissionError("Not your appointment")
    if user and getattr(user, "role", "") == "doctor" and a.doctor_id != user.doctor_id:
        raise PermissionError("Not your appointment")
    _scope_check(user, a.hospital_id)
    return a


async def _get_appointment(db, a, user=None, corr="", idem="", conversation_id=None):
    if not a.get("appointment_id"):
        raise ValueError("appointment_id is required")
    return _serialize_appt(db, _own_appt(db, a["appointment_id"], user))


async def _create_appointment(db, a, user=None, corr="", idem="", conversation_id=None):
    for k in ("hospital_id", "doctor_id", "patient_id", "starts_at", "ends_at"):
        if not a.get(k):
            raise ValueError(f"{k} is required")
    if user and getattr(user, "role", "") == "patient" and int(a["patient_id"]) != user.patient_id:
        raise PermissionError("Cannot book for another patient")
    _scope_check(user, a.get("hospital_id"))
    from app.services.booking import book_appointment
    return await book_appointment(
        db, hospital_id=int(a["hospital_id"]), doctor_id=int(a["doctor_id"]),
        patient_id=int(a["patient_id"]), starts_at=a["starts_at"], ends_at=a["ends_at"],
        calendar_id=a.get("calendar_id"), mode=a.get("mode", "in_person"),
        reason=a.get("reason", ""), idempotency_key=idem or a.get("idempotency_key", ""),
        actor_user_id=_uid(user), conversation_id=conversation_id, corr=corr)


async def _reschedule_appointment(db, a, user=None, corr="", idem="", conversation_id=None):
    if not a.get("appointment_id") or not a.get("new_starts_at") or not a.get("new_ends_at"):
        raise ValueError("appointment_id, new_starts_at, new_ends_at are required")
    from datetime import datetime as _dt
    from app.scheduling.engine import validate_slot
    from app.ehr.mock_client import EHRClient
    from app.services.helpers import transition
    from app.services.workflows import fire_event
    ap = _own_appt(db, a["appointment_id"], user)
    ns = _dt.fromisoformat(str(a["new_starts_at"]).replace("Z", "+00:00"))
    ne = _dt.fromisoformat(str(a["new_ends_at"]).replace("Z", "+00:00"))
    validate_slot(db, ap.doctor_id, ap.calendar_id, ns, ne, ignore_appointment_id=ap.id)
    old = ap.starts_at.isoformat()
    ap.starts_at, ap.ends_at = ns, ne
    try:
        transition(db, ap, "rescheduled", actor=f"user:{_uid(user)}",
                   note=f"{old} -> {ns.isoformat()}", corr=corr)
    except Exception:
        db.commit()
    if ap.external_appointment_id:
        try:
            await EHRClient().update_appointment(
                ap.external_appointment_id, {"starts_at": ns.isoformat(), "ends_at": ne.isoformat()})
            ap.integration_status = "synced"
            db.commit()
        except Exception:
            ap.integration_status = "reconciliation_required"
            db.commit()
    fire_event(db, "appointment.rescheduled", ap.hospital_id, {"appointment_id": ap.id}, corr)
    return {"id": ap.id, "status": ap.status, "starts_at": ap.starts_at.isoformat()}


async def _cancel_appointment(db, a, user=None, corr="", idem="", conversation_id=None):
    if not a.get("appointment_id"):
        raise ValueError("appointment_id is required")
    from app.ehr.mock_client import EHRClient
    from app.services.helpers import transition
    from app.services.workflows import fire_event
    ap = _own_appt(db, a["appointment_id"], user)
    transition(db, ap, "cancelled", actor=f"user:{_uid(user)}",
               note=a.get("reason", "cancelled"), corr=corr)
    if ap.external_appointment_id:
        try:
            await EHRClient().cancel_appointment(ap.external_appointment_id)
        except Exception:
            pass
    fire_event(db, "appointment.cancelled", ap.hospital_id, {"appointment_id": ap.id}, corr)
    return {"id": ap.id, "status": "cancelled"}


async def _get_questionnaire(db, a, user=None, corr="", idem="", conversation_id=None):
    if not a.get("questionnaire_id"):
        raise ValueError("questionnaire_id is required")
    qn = db.query(models.Questionnaire).filter(
        models.Questionnaire.id == int(a["questionnaire_id"])).first()
    if not qn:
        raise ValueError("Questionnaire not found")
    _scope_check(user, qn.hospital_id)
    return {"id": qn.id, "title": qn.title, "schema": qn.schema_json}


async def _submit_questionnaire(db, a, user=None, corr="", idem="", conversation_id=None):
    if not a.get("response_id"):
        raise ValueError("response_id is required")
    r = db.query(models.QuestionnaireResponse).filter(
        models.QuestionnaireResponse.id == int(a["response_id"])).first()
    if not r:
        raise ValueError("Response not found")
    if user and getattr(user, "role", "") == "patient" and r.patient_id != user.patient_id:
        raise PermissionError("Not your questionnaire")
    r.answers_json = json.dumps(a.get("answers", {}))
    r.status = "completed"
    db.commit()
    return {"id": r.id, "status": "completed"}


async def _send_notification(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services.helpers import notify
    n = notify(db, a.get("kind", "ai_message"), a.get("title", "Update"),
               a.get("body", ""), _uid(user), a.get("hospital_id"), "ai", conversation_id)
    return {"id": n.id if n else None, "status": "sent" if n else "failed"}


async def _start_workflow(db, a, user=None, corr="", idem="", conversation_id=None):
    if not a.get("event"):
        raise ValueError("event is required")
    from app.services.workflows import fire_event
    hid = a.get("hospital_id") or getattr(user, "hospital_id", None)
    fire_event(db, a["event"], hid, {"conversation_id": conversation_id, **(a.get("payload") or {})}, corr)
    return {"event": a["event"], "fired": True}


async def _get_context(db, a, user=None, corr="", idem="", conversation_id=None):
    cid = a.get("conversation_id") or conversation_id
    if not cid:
        raise ValueError("conversation_id is required")
    ctx = db.query(models.AIContext).filter(models.AIContext.conversation_id == int(cid)).first()
    if not ctx:
        return {"conversation_id": cid, "slices": {}}
    return {"conversation_id": cid, "slices": {
        "conversational": ctx.conversational, "transactional": ctx.transactional,
        "user_ctx": ctx.user_ctx, "workflow_state": ctx.workflow_state,
        "integration_state": ctx.integration_state}}


async def _update_preferences(db, a, user=None, corr="", idem="", conversation_id=None):
    pref = db.query(models.UserContextPref).filter(
        models.UserContextPref.user_id == _uid(user)).first()
    if not pref:
        pref = models.UserContextPref(user_id=_uid(user), prefs="{}")
        db.add(pref)
    try:
        cur = json.loads(pref.prefs or "{}")
    except Exception:
        cur = {}
    cur.update(a.get("prefs", {}))
    pref.prefs = json.dumps(cur)
    db.commit()
    return {"prefs": cur}


async def _verify_external(db, a, user=None, corr="", idem="", conversation_id=None):
    ap = _own_appt(db, a.get("appointment_id") or a.get("external_id") and -1 or 0, user) \
        if str(a.get("appointment_id", "")).isdigit() else None
    if ap is None:
        ext = str(a.get("external_id", ""))
        if not ext:
            raise ValueError("appointment_id or external_id is required")
        from app.ehr.mock_client import EHRClient
        seen = await EHRClient().get_appointment(ext)
        return {"external_id": ext, "found": bool(seen), "result": "matched" if seen else "not_found"}
    if not ap.external_appointment_id:
        return {"appointment_id": ap.id, "result": "not_found", "detail": "no external id yet"}
    from app.ehr.mock_client import EHRClient
    seen = await EHRClient().get_appointment(ap.external_appointment_id)
    op = models.IntegrationOperation(hospital_id=ap.hospital_id, kind="verify",
                                     ref_type="appointment", ref_id=ap.id,
                                     status="success", correlation_id=corr,
                                     idempotency_key=f"verify-{ap.id}-{corr}")
    db.add(op)
    db.commit()
    result = "matched" if seen else "not_found"
    db.add(models.IntegrationVerification(operation_id=op.id, appointment_id=ap.id,
                                          method="retrieve", result=result,
                                          detail_json=json.dumps({"external": seen} if seen else {}),
                                          correlation_id=corr))
    db.commit()
    return {"appointment_id": ap.id, "result": result}


async def _synchronize_state(db, a, user=None, corr="", idem="", conversation_id=None):
    if not a.get("appointment_id"):
        raise ValueError("appointment_id is required")
    ap = _own_appt(db, a["appointment_id"], user)
    op = db.query(models.IntegrationOperation).filter(
        models.IntegrationOperation.ref_id == ap.id).order_by(
        models.IntegrationOperation.id.desc()).first()
    if not op:
        raise ValueError("no operation to recover")
    from app.services.booking import recover_unknown_outcome
    return await recover_unknown_outcome(db, ap.id, op.id, corr)


async def _transfer_to_human(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services.helpers import ops as _ops
    ap = None
    if a.get("appointment_id"):
        try:
            ap = _own_appt(db, a["appointment_id"], user)
        except Exception:
            ap = None
    hid = (ap.hospital_id if ap else None) or getattr(user, "hospital_id", None)
    rec = models.ReconciliationRecord(hospital_id=hid or 1,
                                      appointment_id=ap.id if ap else None,
                                      issue=a.get("reason", "human_escalation"),
                                      status="open",
                                      resolution=str(a.get("summary", ""))[:2000],
                                      correlation_id=corr)
    db.add(rec)
    db.commit()
    _ops(db, "human.escalation", f"Escalated conv {conversation_id}: {a.get('summary', '')[:200]}",
         "warn", hid, corr, {})
    return {"escalated": True, "queue": "care_team", "rec_id": rec.id}


async def _get_reviews(db, a, user=None, corr="", idem="", conversation_id=None):
    from sqlalchemy import func as _f
    q = db.query(models.Review).filter(models.Review.status == "approved")
    target = a.get("target", "doctor")
    if a.get("doctor_id"):
        q = q.filter(models.Review.doctor_id == int(a["doctor_id"]))
    if a.get("hospital_id"):
        _scope_check(user, a["hospital_id"])
        q = q.filter(models.Review.hospital_id == int(a["hospital_id"]))
    rows = q.order_by(models.Review.id.desc()).limit(10).all()
    n, avg = _review_avg(db, doctor_id=a.get("doctor_id"),
                         hospital_id=a.get("hospital_id"),
                         target=target if not a.get("doctor_id") else "doctor")
    return {"count": n or len(rows), "avg": avg,
            "reviews": [{"rating": r.rating, "title": r.title, "body": r.body[:500]} for r in rows]}


async def _list_my_appointments(db, a, user=None, corr="", idem="", conversation_id=None):
    q = db.query(models.Appointment)
    if user and getattr(user, "role", "") == "patient":
        q = q.filter(models.Appointment.patient_id == user.patient_id)
    elif user and getattr(user, "role", "") == "doctor":
        q = q.filter(models.Appointment.doctor_id == user.doctor_id)
    elif user and getattr(user, "role", "") == "hospital_admin" and getattr(user, "hospital_id", None):
        q = q.filter(models.Appointment.hospital_id == user.hospital_id)
    rows = q.order_by(models.Appointment.starts_at.desc()).limit(20).all()
    return {"appointments": [_serialize_appt(db, r) for r in rows]}


async def _list_my_questionnaires(db, a, user=None, corr="", idem="", conversation_id=None):
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


async def _get_notifications(db, a, user=None, corr="", idem="", conversation_id=None):
    rows = db.query(models.Notification).filter(
        models.Notification.user_id == _uid(user)).order_by(
        models.Notification.id.desc()).limit(20).all()
    return {"notifications": [
        {"id": n.id, "title": n.title, "body": n.body, "status": n.status} for n in rows]}


_IMPL = {
    "search_hospitals": _search_hospitals, "search_doctors": _search_doctors,
    "get_doctor_details": _get_doctor_details, "get_hospital_details": _get_hospital_details,
    "check_availability": _check_availability, "lookup_patient": _lookup_patient,
    "get_appointment": _get_appointment, "create_appointment": _create_appointment,
    "reschedule_appointment": _reschedule_appointment, "cancel_appointment": _cancel_appointment,
    "get_questionnaire": _get_questionnaire, "submit_questionnaire": _submit_questionnaire,
    "send_notification": _send_notification, "start_workflow": _start_workflow,
    "get_context": _get_context, "update_preferences": _update_preferences,
    "verify_external_appointment": _verify_external, "synchronize_state": _synchronize_state,
    "transfer_to_human": _transfer_to_human, "get_reviews": _get_reviews,
    "list_my_appointments": _list_my_appointments, "list_my_questionnaires": _list_my_questionnaires,
    "get_notifications": _get_notifications,
}
