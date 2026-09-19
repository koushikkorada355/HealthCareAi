"""MCP capability layer: typed, validated, authorized, idempotent, audited. AI calls these — never DB/EHR directly."""
import json, time, uuid
from sqlalchemy.orm import Session
from .. import models

CAPABILITIES = [
    {"name":"search_hospitals","description":"Search approved hospitals (supports q, city)","idempotent":True},
    {"name":"search_doctors","description":"Search active doctors (supports specialty, hospital_id, q)","idempotent":True},
    {"name":"get_doctor_details","description":"Full doctor profile: hospital, stats, next slots, reviews summary","idempotent":True},
    {"name":"get_hospital_details","description":"Full hospital profile: departments, doctors, stats, reviews summary","idempotent":True},
    {"name":"check_availability","description":"Real slot lookup (never invented)","idempotent":True},
    {"name":"lookup_patient","description":"Patient lookup","idempotent":True},
    {"name":"get_appointment","description":"Get appointment by id","idempotent":True},
    {"name":"create_appointment","description":"Book with verify+sync","idempotent":True},
    {"name":"reschedule_appointment","description":"Reschedule with revalidation","idempotent":True},
    {"name":"cancel_appointment","description":"Cancel appt + EHR cancel","idempotent":True},
    {"name":"get_questionnaire","description":"Get questionnaire + status","idempotent":True},
    {"name":"submit_questionnaire","description":"Submit structured answers","idempotent":False},
    {"name":"send_notification","description":"Queue notification","idempotent":False},
    {"name":"start_workflow","description":"Trigger workflow","idempotent":False},
    {"name":"get_context","description":"Get conversation context slices","idempotent":True},
    {"name":"update_preferences","description":"Update user prefs","idempotent":False},
    {"name":"verify_external_appointment","description":"Verify against EHR","idempotent":True},
    {"name":"synchronize_state","description":"Sync internal from external","idempotent":True},
    {"name":"transfer_to_human","description":"Escalate to human","idempotent":False},
    {"name":"get_reviews","description":"Approved patient reviews for a doctor or hospital","idempotent":True},
    {"name":"list_my_appointments","description":"Caller's own appointments (role-scoped)","idempotent":True},
    {"name":"get_notifications","description":"Caller's notification inbox","idempotent":True},
]

def _audit_exec(db, conv_id, name, status, inp, out, err, user_id, idem, corr, ms):
    try:
        db.add(models.CapabilityExecution(conversation_id=conv_id, name=name, status=status, input_json=json.dumps(inp)[:4000], output_json=json.dumps(out)[:4000] if out else "", error=(err or "")[:2000], actor_user_id=user_id, idempotency_key=idem or "", correlation_id=corr, latency_ms=ms)); db.commit()
    except Exception: db.rollback()

def _scope_check(user, hospital_id=None):
    if user.role in ("hospital_admin","doctor") and hospital_id and user.hospital_id and int(hospital_id) != int(user.hospital_id):
        raise PermissionError("Cross-tenant denied")

async def invoke(db: Session, name: str, args: dict, *, user, conversation_id=None, idempotency_key="", corr="") -> dict:
    t0 = time.time(); corr = corr or uuid.uuid4().hex[:12]; idem = idempotency_key or args.get("idempotency_key","")
    try:
        fn = _IMPL[name]
    except KeyError:
        _audit_exec(db, conversation_id, name, "failed", args, None, "unknown capability", getattr(user,"id",None), idem, corr, 0)
        raise ValueError(f"Unknown capability {name}")
    try:
        out = await fn(db, args, user=user, corr=corr, idem=idem)
        _audit_exec(db, conversation_id, name, "success", args, out, "", getattr(user,"id",None), idem, corr, int((time.time()-t0)*1000))
        return {"ok": True, "capability": name, "correlation_id": corr, "data": out}
    except PermissionError as e:
        _audit_exec(db, conversation_id, name, "denied", args, None, str(e), getattr(user,"id",None), idem, corr, int((time.time()-t0)*1000))
        raise
    except Exception as e:
        _audit_exec(db, conversation_id, name, "failed", args, None, str(e), getattr(user,"id",None), idem, corr, int((time.time()-t0)*1000))
        raise

async def _search_hospitals(db, a, user=None, corr="", idem=""):
    from sqlalchemy import func as _func
    from ..api.v1.reviews import hospital_review_stats
    q = db.query(models.Hospital).filter(models.Hospital.status=="approved")
    if a.get("city"): q = q.filter(models.Hospital.city.ilike(f"%{a['city']}%"))
    if a.get("q"):
        term = f"%{a['q']}%"
        q = q.filter((models.Hospital.name.ilike(term)) | (models.Hospital.city.ilike(term)))
    try: min_rating = float(a.get("min_rating", 0) or 0)
    except (TypeError, ValueError): min_rating = 0
    sort = (a.get("sort") or "").strip().lower()
    if sort not in ("", "top_rated", "most_reviewed"): raise ValueError("sort must be top_rated|most_reviewed")
    lat = a.get("lat", a.get("latitude")); lng = a.get("lng", a.get("longitude"))
    near = lat is not None and lng is not None and str(lat) != "" and str(lng) != ""
    try: radius = float(a.get("radius_km", 25) or 25)
    except (TypeError, ValueError): radius = 25
    out = []
    for h in q.limit(100).all():
        dcnt = db.query(_func.count(models.Doctor.id)).filter(models.Doctor.hospital_id==h.id, models.Doctor.status=="active").scalar() or 0
        _rc, _ra = hospital_review_stats(db, h.id)
        if _ra < min_rating: continue
        hlat, hlng = getattr(h, "latitude", None), getattr(h, "longitude", None)
        dist = _haversine_km(lat, lng, hlat, hlng) if near else None
        if near and (dist is None or dist > radius): continue
        out.append({"id":h.id,"name":h.name,"city":h.city,"address":h.address,"latitude":hlat,"longitude":hlng,"services":h.services,"cover_url":getattr(h,"cover_url",""),"doctor_count":dcnt,"avg_rating":_ra,"review_count":_rc,"distance_km":dist})
    if sort == "top_rated": out.sort(key=lambda x: (x["avg_rating"], x["review_count"]), reverse=True)
    elif sort == "most_reviewed": out.sort(key=lambda x: (x["review_count"], x["avg_rating"]), reverse=True)
    elif near: out.sort(key=lambda x: (x["distance_km"] is None, x["distance_km"] or 0))
    return {"hospitals": out[:20]}

def _haversine_km(lat1, lng1, lat2, lng2):
    import math
    try:
        lat1, lng1, lat2, lng2 = float(lat1), float(lng1), float(lat2), float(lng2)
    except (TypeError, ValueError):
        return None
    r = 6371.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = math.radians(lat2 - lat1), math.radians(lng2 - lng1)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return round(2 * r * math.asin(math.sqrt(h)), 1)
async def _search_doctors(db, a, user=None, corr="", idem=""):
    q = db.query(models.Doctor).filter(models.Doctor.status=="active")
    _scope_check(user, a.get("hospital_id"))
    if a.get("hospital_id"): q = q.filter(models.Doctor.hospital_id==int(a["hospital_id"]))
    elif user and user.role in ("hospital_admin","doctor") and user.hospital_id: q = q.filter(models.Doctor.hospital_id==user.hospital_id)
    if a.get("specialty"): q = q.join(models.Specialty, models.Specialty.id==models.Doctor.specialty_id, isouter=True).filter(models.Specialty.name.ilike(f"%{a['specialty']}%"))
    if a.get("q"): q = q.filter(models.Doctor.name.ilike(f"%{a['q']}%"))
    ds = q.limit(100).all()
    out = []
    from ..api.v1.reviews import doctor_review_stats
    try: min_rating = float(a.get("min_rating", 0) or 0)
    except (TypeError, ValueError): min_rating = 0
    sort = (a.get("sort") or "").strip().lower()
    if sort not in ("", "top_rated", "most_reviewed", "most_experienced"): raise ValueError("sort must be top_rated|most_reviewed|most_experienced")
    for d in ds:
        sp = db.query(models.Specialty).filter(models.Specialty.id==d.specialty_id).first() if d.specialty_id else None
        h = db.query(models.Hospital).filter(models.Hospital.id==d.hospital_id).first()
        _rc, _ra = doctor_review_stats(db, d.id)
        if _ra < min_rating: continue
        out.append({"id":d.id,"name":d.name,"hospital_id":d.hospital_id,"hospital_name":h.name if h else "","hospital_city":h.city if h else "","specialty":sp.name if sp else "","experience_years":d.experience_years,"rating":d.rating,"review_count":_rc,"avg_rating":_ra,"photo_url":d.photo_url,"duration_minutes":d.duration_minutes})
    if sort == "top_rated": out.sort(key=lambda x: (x["avg_rating"], x["review_count"]), reverse=True)
    elif sort == "most_reviewed": out.sort(key=lambda x: (x["review_count"], x["avg_rating"]), reverse=True)
    elif sort == "most_experienced": out.sort(key=lambda x: (x["experience_years"] or 0), reverse=True)
    return {"doctors": out[:20]}
async def _get_doctor_details(db, a, user=None, corr="", idem=""):
    from sqlalchemy import func as _func
    from datetime import datetime, timezone, timedelta
    from ..api.v1.reviews import doctor_review_stats
    did = int(a.get("doctor_id") or a.get("id") or 0)
    if a.get("name") and not did:
        d = db.query(models.Doctor).filter(models.Doctor.status=="active", models.Doctor.name.ilike(f"%{a['name']}%")).first()
    else:
        d = db.query(models.Doctor).filter(models.Doctor.id==did).first()
    if not d: raise ValueError("Doctor not found")
    _scope_check(user, d.hospital_id)
    sp = db.query(models.Specialty).filter(models.Specialty.id==d.specialty_id).first() if d.specialty_id else None
    h = db.query(models.Hospital).filter(models.Hospital.id==d.hospital_id).first()
    completed = db.query(_func.count(models.Appointment.id)).filter(models.Appointment.doctor_id==d.id, models.Appointment.status=="completed").scalar() or 0
    _rc, _ra = doctor_review_stats(db, d.id)
    _sum = f"★ {_ra} from {_rc} review(s)" if _rc else "No patient reviews yet — be the first after a completed visit."
    next_slots = []
    try:
        from ..scheduling.engine import compute_slots
        base = datetime.now(timezone.utc)
        for i in range(3):
            next_slots += compute_slots(db, d.id, base + timedelta(days=i), None)
            if len(next_slots) >= 3: break
        next_slots = next_slots[:3]
    except Exception:
        next_slots = []
    return {"id":d.id,"name":d.name,"hospital_id":d.hospital_id,"hospital_name":h.name if h else "","hospital_city":h.city if h else "","specialty":sp.name if sp else "","qualifications":d.qualifications,"experience_years":d.experience_years,"languages":d.languages,"consultation_types":d.consultation_types,"duration_minutes":d.duration_minutes,"status":d.status,"photo_url":d.photo_url,"rating":d.rating,"review_count":_rc,"avg_rating":_ra,"completed_visits":completed,"next_slots":next_slots,"reviews_summary":_sum}
async def _get_hospital_details(db, a, user=None, corr="", idem=""):
    from sqlalchemy import func as _func
    from ..api.v1.reviews import hospital_review_stats
    hid = int(a.get("hospital_id") or a.get("id") or 0)
    if a.get("name") and not hid:
        h = db.query(models.Hospital).filter(models.Hospital.status=="approved", models.Hospital.name.ilike(f"%{a['name']}%")).first()
    else:
        h = db.query(models.Hospital).filter(models.Hospital.id==hid).first()
    if not h: raise ValueError("Hospital not found")
    depts = [{"id":x.id,"name":x.name} for x in db.query(models.Department).filter(models.Department.hospital_id==h.id).all()]
    docs = db.query(models.Doctor).filter(models.Doctor.hospital_id==h.id, models.Doctor.status=="active").all()
    top = []
    for d in docs[:8]:
        sp = db.query(models.Specialty).filter(models.Specialty.id==d.specialty_id).first() if d.specialty_id else None
        top.append({"id":d.id,"name":d.name,"specialty":sp.name if sp else "","rating":d.rating,"photo_url":d.photo_url})
    completed = db.query(_func.count(models.Appointment.id)).filter(models.Appointment.hospital_id==h.id, models.Appointment.status=="completed").scalar() or 0
    _rc, _ra = hospital_review_stats(db, h.id)
    _sum = f"★ {_ra} from {_rc} review(s)" if _rc else "No patient reviews yet."
    return {"id":h.id,"name":h.name,"slug":h.slug,"city":h.city,"address":h.address,"latitude":getattr(h,"latitude",None),"longitude":getattr(h,"longitude",None),"phone":h.phone,"operating_hours":h.operating_hours,"services":h.services,"cover_url":getattr(h,"cover_url",""),"departments":depts,"doctor_count":len(docs),"doctors":top,"avg_rating":_ra,"review_count":_rc,"completed_visits":completed,"reviews_summary":_sum}
async def _check_availability(db, a, user=None, corr="", idem=""):
    from ..scheduling.engine import compute_slots
    from datetime import datetime, timezone, timedelta
    did = int(a["doctor_id"]); days = int(a.get("days_ahead", 7))
    dur = a.get("duration_minutes")
    session = (a.get("session") or "").strip().lower()
    if session not in ("", "morning", "afternoon", "evening"): raise ValueError("session must be morning|afternoon|evening")
    day_list = []
    if a.get("date"):
        try:
            one = datetime.fromisoformat(str(a["date"])[:10]).replace(tzinfo=timezone.utc)
        except ValueError:
            raise ValueError("date must be YYYY-MM-DD")
        day_list = [one]
    else:
        base = datetime.now(timezone.utc)
        day_list = [base + timedelta(days=i) for i in range(days)]
    def in_session(iso):
        if not session: return True
        h = datetime.fromisoformat(iso).hour
        return (h < 12) if session == "morning" else ((12 <= h < 17) if session == "afternoon" else (h >= 17))
    slots = []
    for day in day_list:
        for s in compute_slots(db, did, day, dur):
            if in_session(s["starts_at"]): slots.append(s)
            if len(slots) >= 24: break
        if len(slots) >= 24: break
    return {"doctor_id": did, "slots": slots[:24], "count": len(slots[:24]), "source": "scheduling_engine"}
async def _lookup_patient(db, a, user=None, corr="", idem=""):
    p = None
    if a.get("patient_id"): p = db.query(models.Patient).filter(models.Patient.id==int(a["patient_id"])).first()
    elif a.get("email"): p = db.query(models.Patient).filter(models.Patient.email==a["email"]).first()
    if not p: return {"found": False}
    if user and user.role=="patient":
        me = db.query(models.Patient).filter(models.Patient.id==user.patient_id).first() if user.patient_id else None
        if not me or me.id != p.id: raise PermissionError("Patients may only look up themselves")
    return {"found": True, "patient": {"id": p.id, "full_name": p.full_name, "external_patient_id": p.external_patient_id}}
async def _get_appointment(db, a, user=None, corr="", idem=""):
    ap = db.query(models.Appointment).filter(models.Appointment.id==int(a["appointment_id"])).first()
    if not ap: raise ValueError("Appointment not found")
    _scope_check(user, ap.hospital_id)
    if user and user.role=="patient" and ap.patient_id != user.patient_id: raise PermissionError("Not your appointment")
    if user and user.role=="doctor" and ap.doctor_id != user.doctor_id: raise PermissionError("Not your appointment")
    return {"id":ap.id,"status":ap.status,"starts_at":ap.starts_at.isoformat(),"ends_at":ap.ends_at.isoformat(),"doctor_id":ap.doctor_id,"hospital_id":ap.hospital_id,"external_id":ap.external_appointment_id,"integration_status":ap.integration_status}
async def _create_appointment(db, a, user=None, corr="", idem=""):
    from ..services.booking import book_appointment
    if user and user.role=="patient" and int(a["patient_id"]) != int(user.patient_id or 0): raise PermissionError("Cannot book for another patient")
    _scope_check(user, a.get("hospital_id"))
    return await book_appointment(db, hospital_id=int(a["hospital_id"]), doctor_id=int(a["doctor_id"]), patient_id=int(a["patient_id"]), starts_at=a["starts_at"], ends_at=a["ends_at"], calendar_id=a.get("calendar_id"), appointment_type_id=a.get("appointment_type_id"), mode=a.get("mode","in_person"), reason=a.get("reason",""), idempotency_key=idem or a.get("idempotency_key",""), actor_user_id=getattr(user,"id",None), conversation_id=a.get("conversation_id"), simulate=a.get("simulate",""), corr=corr)
async def _reschedule(db, a, user=None, corr="", idem=""):
    from ..scheduling.engine import validate_slot
    from ..ehr.mock_client import EHRClient
    from ..services.helpers import transition, audit
    ap = db.query(models.Appointment).filter(models.Appointment.id==int(a["appointment_id"])).first()
    if not ap: raise ValueError("Not found")
    _scope_check(user, ap.hospital_id)
    from datetime import datetime
    ns = datetime.fromisoformat(str(a["new_starts_at"]).replace("Z","+00:00")); ne = datetime.fromisoformat(str(a["new_ends_at"]).replace("Z","+00:00"))
    validate_slot(db, ap.doctor_id, ap.calendar_id, ns, ne, ignore_appointment_id=ap.id)
    old = ap.starts_at.isoformat()
    ap.starts_at, ap.ends_at = ns, ne
    try: transition(db, ap, "rescheduled", actor=f"user:{getattr(user,'id','')}", note=f"{old} -> {ns.isoformat()}", corr=corr)
    except Exception: db.commit()
    if ap.external_appointment_id:
        try:
            await EHRClient().update_appointment(ap.external_appointment_id, {"starts_at": ns.isoformat(), "ends_at": ne.isoformat()})
            ap.integration_status = "synced"; db.commit()
        except Exception as e: ap.integration_status = "reconciliation_required"; db.commit()
    from ..services.workflows import fire_event
    fire_event(db, "appointment.rescheduled", ap.hospital_id, {"appointment_id": ap.id}, corr)
    return {"id": ap.id, "status": ap.status, "starts_at": ap.starts_at.isoformat()}
async def _cancel(db, a, user=None, corr="", idem=""):
    from ..ehr.mock_client import EHRClient
    from ..services.helpers import transition
    ap = db.query(models.Appointment).filter(models.Appointment.id==int(a["appointment_id"])).first()
    if not ap: raise ValueError("Not found")
    _scope_check(user, ap.hospital_id)
    if user and user.role=="patient" and ap.patient_id != user.patient_id: raise PermissionError("Not your appointment")
    transition(db, ap, "cancelled", actor=f"user:{getattr(user,'id','')}", note=a.get("reason","cancelled"), corr=corr)
    if ap.external_appointment_id:
        try: await EHRClient().cancel_appointment(ap.external_appointment_id)
        except Exception: pass
    from ..services.workflows import fire_event
    fire_event(db, "appointment.cancelled", ap.hospital_id, {"appointment_id": ap.id}, corr)
    return {"id": ap.id, "status": "cancelled"}
async def _get_q(db, a, user=None, corr="", idem=""):
    q = db.query(models.Questionnaire).filter(models.Questionnaire.id==int(a["questionnaire_id"])).first()
    import json as J
    return {"id": q.id, "title": q.title, "schema": J.loads(q.schema_json or "[]")}
async def _submit_q(db, a, user=None, corr="", idem=""):
    import json as J
    r = db.query(models.QuestionnaireResponse).filter(models.QuestionnaireResponse.id==int(a["response_id"])).first()
    if not r: raise ValueError("Response not found")
    r.answers_json = J.dumps(a.get("answers", {})); r.status = "completed"; r.collected_via = a.get("via","ai_chat"); db.commit()
    from ..services.workflows import fire_event
    ap = db.query(models.Appointment).filter(models.Appointment.id==r.appointment_id).first() if r.appointment_id else None
    fire_event(db, "questionnaire.completed", ap.hospital_id if ap else None, {"response_id": r.id}, corr)
    return {"id": r.id, "status": "completed"}
async def _send_notif(db, a, user=None, corr="", idem=""):
    from ..services.helpers import notify
    n = notify(db, a.get("kind","update"), a.get("title","Notification"), a.get("body",""), a.get("user_id"), a.get("hospital_id"), a.get("ref_type",""), a.get("ref_id"))
    return {"id": n.id if n else None, "status": "sent"}
async def _start_wf(db, a, user=None, corr="", idem=""):
    from ..services.workflows import fire_event
    fire_event(db, a["event"], a.get("hospital_id"), a.get("payload", {}), corr)
    return {"started": True, "event": a["event"]}
async def _get_ctx(db, a, user=None, corr="", idem=""):
    import json as J
    c = db.query(models.AIContext).filter(models.AIContext.conversation_id==int(a["conversation_id"])).first()
    if not c: return {"conversational":{},"transactional":{},"user":{},"workflow":{},"integration":{}}
    return {"conversational": J.loads(c.conversational or "{}"), "transactional": J.loads(c.transactional or "{}"), "user": J.loads(c.user_ctx or "{}"), "workflow": J.loads(c.workflow_state or "{}"), "integration": J.loads(c.integration_state or "{}")}
async def _upd_prefs(db, a, user=None, corr="", idem=""):
    import json as J
    row = db.query(models.UserContextPref).filter(models.UserContextPref.user_id==user.id).first()
    if not row: row = models.UserContextPref(user_id=user.id, prefs="{}"); db.add(row); db.commit()
    cur = J.loads(row.prefs or "{}"); cur.update(a.get("prefs", {})); row.prefs = J.dumps(cur); db.commit()
    return {"prefs": cur}
async def _verify(db, a, user=None, corr="", idem=""):
    from ..ehr.mock_client import EHRClient
    seen = await EHRClient().get_appointment(a["external_id"])
    return {"found": bool(seen), "external": seen}
async def _sync(db, a, user=None, corr="", idem=""):
    import json as J
    ap = db.query(models.Appointment).filter(models.Appointment.id==int(a["appointment_id"])).first()
    ext = a.get("external", {})
    if ext.get("id"): ap.external_appointment_id = ext["id"]
    ap.integration_status = "synced"; db.commit()
    db.add(models.IntegrationVerification(operation_id=a.get("operation_id", 0), appointment_id=ap.id, method="manual_sync", result="matched", detail_json=J.dumps(ext), correlation_id=corr)); db.commit()
    return {"id": ap.id, "integration_status": "synced"}
async def _transfer(db, a, user=None, corr="", idem=""):
    from ..services.helpers import ops
    ops(db, "human_escalation", a.get("reason","escalated"), "warn", a.get("hospital_id"), corr, {})
    return {"escalated": True, "queue": "care-ops"}
async def _get_reviews(db, a, user=None, corr="", idem=""):
    from ..api.v1.reviews import doctor_review_stats, hospital_review_stats
    limit = max(1, min(int(a.get("limit", 10)), 50))
    stars = a.get("stars")
    if a.get("doctor_id"):
        d = db.query(models.Doctor).filter(models.Doctor.id==int(a["doctor_id"])).first()
        if not d: raise ValueError("Doctor not found")
        _scope_check(user, d.hospital_id)
        q = db.query(models.Review).filter(models.Review.doctor_id==d.id, models.Review.status=="approved")
        if stars: q = q.filter(models.Review.rating==int(stars))
        rows = q.order_by(models.Review.id.desc()).limit(limit).all()
        n, avg = doctor_review_stats(db, d.id)
    elif a.get("hospital_id"):
        hid = int(a["hospital_id"])
        _scope_check(user, hid)
        q = db.query(models.Review).filter(models.Review.hospital_id==hid, models.Review.status=="approved")
        if stars: q = q.filter(models.Review.rating==int(stars))
        rows = q.order_by(models.Review.id.desc()).limit(limit).all()
        n, avg = hospital_review_stats(db, hid)
    else:
        raise ValueError("doctor_id or hospital_id is required")
    out = []
    for r in rows:
        p = db.query(models.Patient).filter(models.Patient.id==r.patient_id).first()
        out.append({"id":r.id,"rating":r.rating,"title":r.title,"body":(r.body or "")[:500],"response_text":(r.response_text or "")[:500],"patient_name":p.full_name if p else "","created_at":r.created_at.isoformat() if r.created_at else None})
    return {"count":n,"avg":avg,"reviews":out}
async def _list_mine(db, a, user=None, corr="", idem=""):
    limit = max(1, min(int(a.get("limit", 20)), 100))
    upcoming_only = bool(a.get("upcoming_only", False))
    status = (a.get("status") or "").strip()
    from datetime import datetime, timezone
    q = db.query(models.Appointment)
    if user.role == "patient":
        q = q.filter(models.Appointment.patient_id==user.patient_id)
    elif user.role == "doctor":
        q = q.filter(models.Appointment.doctor_id==user.doctor_id)
    elif user.role == "hospital_admin" and user.hospital_id:
        q = q.filter(models.Appointment.hospital_id==user.hospital_id)
    elif user.role == "platform_admin":
        if not a.get("hospital_id"): raise ValueError("hospital_id is required for platform scope")
        q = q.filter(models.Appointment.hospital_id==int(a["hospital_id"]))
    else:
        raise PermissionError("No scope for this role")
    if status: q = q.filter(models.Appointment.status==status)
    if upcoming_only: q = q.filter(models.Appointment.starts_at>=datetime.now(timezone.utc))
    rows = q.order_by(models.Appointment.starts_at.desc()).limit(limit).all()
    out = []
    for ap in rows:
        d = db.query(models.Doctor).filter(models.Doctor.id==ap.doctor_id).first()
        p = db.query(models.Patient).filter(models.Patient.id==ap.patient_id).first()
        h = db.query(models.Hospital).filter(models.Hospital.id==ap.hospital_id).first()
        out.append({"id":ap.id,"status":ap.status,"starts_at":ap.starts_at.isoformat(),"ends_at":ap.ends_at.isoformat(),"doctor_name":d.name if d else "","patient_name":p.full_name if p else "","hospital_name":h.name if h else "","via_ai":bool(ap.conversation_id)})
    return {"appointments":out,"count":len(out)}
async def _get_notifs(db, a, user=None, corr="", idem=""):
    limit = max(1, min(int(a.get("limit", 20)), 100))
    q = db.query(models.Notification)
    if user.role == "hospital_admin" and user.hospital_id:
        q = q.filter((models.Notification.user_id==user.id)|(models.Notification.hospital_id==user.hospital_id))
    elif user.role == "platform_admin":
        pass
    else:
        q = q.filter(models.Notification.user_id==user.id)
    rows = q.order_by(models.Notification.id.desc()).limit(limit).all()
    return {"notifications":[{"id":n.id,"kind":n.kind,"title":n.title,"body":(n.body or "")[:300],"status":n.status,"hospital_id":n.hospital_id} for n in rows]}

_IMPL = {"search_hospitals":_search_hospitals,"search_doctors":_search_doctors,"get_doctor_details":_get_doctor_details,"get_hospital_details":_get_hospital_details,"check_availability":_check_availability,"lookup_patient":_lookup_patient,"get_appointment":_get_appointment,"create_appointment":_create_appointment,"reschedule_appointment":_reschedule,"cancel_appointment":_cancel,"get_questionnaire":_get_q,"submit_questionnaire":_submit_q,"send_notification":_send_notif,"start_workflow":_start_wf,"get_context":_get_ctx,"update_preferences":_upd_prefs,"verify_external_appointment":_verify,"synchronize_state":_sync,"transfer_to_human":_transfer,"get_reviews":_get_reviews,"list_my_appointments":_list_mine,"get_notifications":_get_notifs}
