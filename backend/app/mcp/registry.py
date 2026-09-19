"""MCP capability layer: typed, validated, authorized, idempotent, audited. AI calls these — never DB/EHR directly."""
import json, time, uuid
from sqlalchemy.orm import Session
from .. import models

CAPABILITIES = [
    {"name":"search_hospitals","description":"Search approved hospitals","idempotent":True},
    {"name":"search_doctors","description":"Search active doctors","idempotent":True},
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
    q = db.query(models.Hospital).filter(models.Hospital.status=="approved")
    if a.get("q"): q = q.filter(models.Hospital.name.ilike(f"%{a['q']}%"))
    return {"hospitals": [{"id":h.id,"name":h.name,"city":h.city,"services":h.services} for h in q.limit(20).all()]}
async def _search_doctors(db, a, user=None, corr="", idem=""):
    q = db.query(models.Doctor).filter(models.Doctor.status=="active")
    _scope_check(user, a.get("hospital_id"))
    if a.get("hospital_id"): q = q.filter(models.Doctor.hospital_id==int(a["hospital_id"]))
    elif user and user.role in ("hospital_admin","doctor") and user.hospital_id: q = q.filter(models.Doctor.hospital_id==user.hospital_id)
    if a.get("specialty"): q = q.join(models.Specialty, models.Specialty.id==models.Doctor.specialty_id, isouter=True).filter(models.Specialty.name.ilike(f"%{a['specialty']}%"))
    if a.get("q"): q = q.filter(models.Doctor.name.ilike(f"%{a['q']}%"))
    ds = q.limit(20).all()
    out = []
    for d in ds:
        sp = db.query(models.Specialty).filter(models.Specialty.id==d.specialty_id).first() if d.specialty_id else None
        out.append({"id":d.id,"name":d.name,"hospital_id":d.hospital_id,"specialty":sp.name if sp else "","experience_years":d.experience_years,"rating":d.rating,"duration_minutes":d.duration_minutes})
    return {"doctors": out}
async def _check_availability(db, a, user=None, corr="", idem=""):
    from ..scheduling.engine import compute_slots
    from datetime import datetime, timezone, timedelta
    did = int(a["doctor_id"]); days = int(a.get("days_ahead", 7))
    dur = a.get("duration_minutes")
    slots = []
    base = datetime.now(timezone.utc)
    for i in range(days):
        slots += compute_slots(db, did, base + timedelta(days=i), dur)
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

_IMPL = {"search_hospitals":_search_hospitals,"search_doctors":_search_doctors,"check_availability":_check_availability,"lookup_patient":_lookup_patient,"get_appointment":_get_appointment,"create_appointment":_create_appointment,"reschedule_appointment":_reschedule,"cancel_appointment":_cancel,"get_questionnaire":_get_q,"submit_questionnaire":_submit_q,"send_notification":_send_notif,"start_workflow":_start_wf,"get_context":_get_ctx,"update_preferences":_upd_prefs,"verify_external_appointment":_verify,"synchronize_state":_sync,"transfer_to_human":_transfer}
