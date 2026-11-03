"""MCP capability registry: typed, validated, authorized, idempotent, audited.

AI calls these — never DB directly. Every invoke writes a
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
    {"name": "check_availability", "description": "Real slots from scheduling engine (doctor_id, date ISO, days 1-14, day_part=morning|afternoon|evening; doctor_name accepted as fallback and resolved server-side)", "idempotent": True},
    {"name": "lookup_patient", "description": "Patient lookup by name (own record for patients)", "idempotent": True},
    {"name": "get_appointment", "description": "Get appointment by id (ownership enforced)", "idempotent": True},
    {"name": "create_appointment", "description": "Book with slot validation (hospital_id, doctor_id, patient_id, starts_at, ends_at)", "idempotent": True},
    {"name": "reschedule_appointment", "description": "Reschedule with revalidation", "idempotent": True},
    {"name": "cancel_appointment", "description": "Cancel appointment", "idempotent": True},
    {"name": "get_questionnaire", "description": "Get questionnaire + caller status", "idempotent": True},
    {"name": "submit_questionnaire", "description": "Submit structured answers (response_id, answers)", "idempotent": False},
    {"name": "send_notification", "description": "Queue notification (title, body)", "idempotent": False},
    {"name": "start_workflow", "description": "Trigger workflow event", "idempotent": False},
    {"name": "get_context", "description": "Get conversation context slices", "idempotent": True},
    {"name": "update_preferences", "description": "Update caller prefs", "idempotent": False},
    {"name": "transfer_to_human", "description": "Log a tracked request for the care team (returns reference id, visible on ops dashboards). No live agent exists.", "idempotent": False},
    {"name": "get_reviews", "description": "Approved reviews for doctor/hospital + avg", "idempotent": True},
    {"name": "list_my_appointments", "description": "Caller's own appointments (role-scoped; filters: status, upcoming=true)", "idempotent": True},
    {"name": "list_my_questionnaires", "description": "Caller's pending/due questionnaires with appointment links", "idempotent": True},
    {"name": "get_notifications", "description": "Caller's notification inbox (filter: unread_only=true)", "idempotent": True},
    {"name": "find_next_available", "description": "Earliest real slots across doctors (specialty, hospital/hospital_id, date ISO, days 1-14, day_part, limit 1-20). Never invents times.", "idempotent": True},
    {"name": "get_hospital_info", "description": "Full hospital profile: contact, services, hours, departments, specialties, doctors, ratings", "idempotent": True},
    {"name": "list_specialties", "description": "Specialties for a hospital (hospital_id optional)", "idempotent": True},
    {"name": "list_departments", "description": "Departments for a hospital (hospital_id required)", "idempotent": True},
    {"name": "list_appointment_types", "description": "Visit types with duration + modes (hospital_id optional)", "idempotent": True},
    {"name": "get_appointment_details", "description": "Appointment with status history + verification results (ownership enforced)", "idempotent": True},
    {"name": "submit_review", "description": "Patient rates a completed visit (appointment_id, target_type=doctor|hospital, rating 1-5, title?, body?)", "idempotent": False},
    {"name": "get_my_profile", "description": "Caller's own profile (patient contact fields included)", "idempotent": True},
    {"name": "update_my_profile", "description": "Self-service profile edit (full_name, phone, dob, gender, address). Email locked.", "idempotent": False},
    {"name": "get_my_dashboard", "description": "Patient one-call summary: upcoming visit, total count, questionnaires due", "idempotent": True},
    {"name": "list_questionnaires", "description": "Browse active questionnaires (hospital_id optional)", "idempotent": True},
]

# ---- Single source of truth for tool contracts + policies ----
# Adding a new tool = append here + add its impl + _IMPL entry.
# Planner, router, resolver, executor and response all read these
# dynamically; no shared component may name individual tools.
TOOL_SCHEMAS: dict[str, dict] = {
    "search_hospitals": {"required": [], "int_args": []},
    "search_doctors": {"required": [], "int_args": ["hospital_id"]},
    "get_doctor_details": {"required": [], "int_args": ["doctor_id"]},
    "get_hospital_details": {"required": [], "int_args": ["hospital_id"]},
    "check_availability": {"required": ["doctor_id"], "int_args": ["doctor_id"]},
    "lookup_patient": {"required": [], "int_args": []},
    "get_appointment": {"required": ["appointment_id"], "int_args": ["appointment_id"]},
    "create_appointment": {"required": ["hospital_id", "doctor_id", "patient_id", "starts_at", "ends_at"],
                           "int_args": ["hospital_id", "doctor_id", "patient_id"]},
    "reschedule_appointment": {"required": ["appointment_id", "new_starts_at", "new_ends_at"],
                               "int_args": ["appointment_id"]},
    "cancel_appointment": {"required": ["appointment_id"], "int_args": ["appointment_id"]},
    "get_questionnaire": {"required": ["questionnaire_id"], "int_args": ["questionnaire_id"]},
    "submit_questionnaire": {"required": ["response_id"], "int_args": ["response_id"]},
    "send_notification": {"required": [], "int_args": []},
    "start_workflow": {"required": ["event"], "int_args": []},
    "get_context": {"required": ["conversation_id"], "int_args": ["conversation_id"]},
    "update_preferences": {"required": [], "int_args": []},
    "transfer_to_human": {"required": [], "int_args": []},
    "get_reviews": {"required": [], "int_args": ["doctor_id", "hospital_id", "rating"]},
    "list_my_appointments": {"required": [], "int_args": []},
    "list_my_questionnaires": {"required": ["patient_id"], "int_args": ["patient_id"]},
    "get_notifications": {"required": [], "int_args": []},
    "find_next_available": {"required": [], "int_args": ["hospital_id", "days", "limit"]},
    "get_hospital_info": {"required": ["hospital_id"], "int_args": ["hospital_id"]},
    "list_specialties": {"required": [], "int_args": ["hospital_id"]},
    "list_departments": {"required": ["hospital_id"], "int_args": ["hospital_id"]},
    "list_appointment_types": {"required": [], "int_args": ["hospital_id"]},
    "get_appointment_details": {"required": ["appointment_id"], "int_args": ["appointment_id"]},
    "submit_review": {"required": ["appointment_id", "target_type", "rating"], "int_args": ["appointment_id", "rating"]},
    "get_my_profile": {"required": [], "int_args": []},
    "update_my_profile": {"required": [], "int_args": []},
    "get_my_dashboard": {"required": [], "int_args": []},
    "list_questionnaires": {"required": [], "int_args": ["hospital_id"]},
}

TOOL_POLICIES: dict[str, dict] = {
    # approval_required: pause via LangGraph interrupt before executing.
    # retryable/timeout_s/parallel_safe drive the generic executor.
    "default": {"idempotent": True, "approval_required": False,
                "retryable": True, "timeout_s": 25, "parallel_safe": True},
    "create_appointment": {"idempotent": True, "approval_required": False,
                           "retryable": False, "timeout_s": 25, "parallel_safe": False},
    "reschedule_appointment": {"idempotent": True, "approval_required": False,
                               "retryable": False, "timeout_s": 25, "parallel_safe": False},
    "cancel_appointment": {"idempotent": True, "approval_required": True,
                           "retryable": False, "timeout_s": 25, "parallel_safe": False},
    "submit_questionnaire": {"idempotent": False, "approval_required": False,
                             "retryable": False, "timeout_s": 25, "parallel_safe": False},
    "transfer_to_human": {"idempotent": False, "approval_required": False,
                          "retryable": False, "timeout_s": 25, "parallel_safe": False},
    "find_next_available": {"idempotent": True, "approval_required": False,
                            "retryable": True, "timeout_s": 30, "parallel_safe": True},
    "submit_review": {"idempotent": False, "approval_required": False,
                      "retryable": False, "timeout_s": 25, "parallel_safe": False},
    "update_my_profile": {"idempotent": False, "approval_required": False,
                          "retryable": False, "timeout_s": 25, "parallel_safe": False},
    "get_my_dashboard": {"idempotent": True, "approval_required": False,
                         "retryable": True, "timeout_s": 25, "parallel_safe": True},
}


def tool_names() -> list[str]:
    return [t["name"] for t in CAPABILITIES]


# ---- Per-tool UI action templates (presentation metadata, not logic) ----
# The generic card builder renders follow-up buttons from these templates,
# filling {name}/{where}/{ref}/{title} from the item's own fields. Adding a
# tool with custom button text = one entry here; shared code stays untouched.
TOOL_ACTIONS: dict[str, dict] = {
    "check_availability": {"label": "Check availability",
                            "text": "Check availability for {name}{where}"},
    "create_appointment": {"label": "Book",
                            "text": "Book appointment with {name}{where}"},
    "get_doctor_details": {"label": "Details", "text": "Show details of {name}{where}"},
    "get_hospital_details": {"label": "Details", "text": "Show details of {name}"},
    "search_doctors": {"label": "View doctors", "text": "Show doctors at {name}"},
    "get_appointment": {"label": "Details", "text": "Details of appointment #{ref}"},
    "cancel_appointment": {"label": "Cancel", "text": "Cancel appointment #{ref}"},
    "reschedule_appointment": {"label": "Reschedule", "text": "Reschedule appointment #{ref}"},
    "get_questionnaire": {"label": "Open", "text": "Open questionnaire {title}"},
    "list_my_questionnaires": {"label": "Open", "text": "Open questionnaire {title}"},
    "submit_questionnaire": {"label": "Open", "text": "Open questionnaire {title}"},
    "list_my_appointments": {"label": "My visits", "text": "Show my appointments"},
    "find_next_available": {"label": "Find slots",
                           "text": "Find next available for {name}{where}"},
    "get_hospital_info": {"label": "Hospital info", "text": "Show info for {name}"},
    "get_appointment_details": {"label": "Details", "text": "Details of appointment #{ref}"},
    "submit_review": {"label": "Review", "text": "Review appointment #{ref}"},
    "get_my_profile": {"label": "My profile", "text": "Show my profile"},
    "get_my_dashboard": {"label": "My summary", "text": "Show my visit summary"},
    "list_questionnaires": {"label": "Open", "text": "Open questionnaire {title}"},
    "list_specialties": {"label": "Specialties", "text": "Show specialties at {name}"},
    "list_departments": {"label": "Departments", "text": "Show departments at {name}"},
    "list_appointment_types": {"label": "Visit types", "text": "Show visit types at {name}"},
}


def get_action_template(tool: str) -> dict | None:
    return TOOL_ACTIONS.get(tool)


def get_schema(name: str) -> dict:
    return TOOL_SCHEMAS.get(name, {"required": [], "int_args": []})


def get_policy(name: str) -> dict:
    base = dict(TOOL_POLICIES.get("default", {}))
    base.update(TOOL_POLICIES.get(name, {}))
    for t in CAPABILITIES:
        if t["name"] == name:
            base["idempotent"] = t.get("idempotent", base.get("idempotent", True))
            break
    return base


def describe_catalog() -> str:
    """Generic planner catalog built from registered tools (no hardcoding)."""
    lines = []
    for t in CAPABILITIES:
        req = ", ".join(get_schema(t["name"]).get("required", [])) or "none"
        lines.append(f"- {t['name']}: {t['description']} [required: {req}]")
    return "\n".join(lines)


def clean_tokens(text: str) -> list[str]:
    """Generic tokenizer: lowercase, drop leading honorifics (any short
    `xx.` token), strip punctuation. No language-specific word lists."""
    parts = str(text or "").lower().split()
    out = []
    for i, p in enumerate(parts):
        q = p.strip(".,;:!?\"'()[]")
        if not q:
            continue
        if i == 0 and p.endswith(".") and len(q) <= 4:
            continue
        out.append(q)
    return out


def token_match(hay: str, needle: str) -> bool:
    hay_l = f" {(hay or '').lower()} "
    toks = clean_tokens(needle)
    return bool(toks) and all(t in hay_l for t in toks)


def resolve_doctor_id(db, *, doctor_name: str = "", hospital_id: int = 0,
                      limit: int = 200) -> int:
    """Generic name -> active-doctor id (any language). Tool-level helper so
    any capability accepting a doctor name resolves it the same way."""
    needle = str(doctor_name or "").strip()
    if not needle or db is None:
        return 0
    try:
        from app.models import Doctor as _D
        q = db.query(_D).filter(_D.status == "active")
        try:
            hid = int(hospital_id or 0)
        except (TypeError, ValueError):
            hid = 0
        if hid:
            q = q.filter(_D.hospital_id == hid)
        for row in q.limit(limit).all():
            if token_match(row.name or "", needle):
                return int(row.id)
    except Exception:
        pass
    return 0


def pick_verified_slot(slots: list, *, doctor_id: int = 0, date_iso: str = "",
                       start_hr=None, end_hr=None) -> dict:
    """Generic verified-slot picker: filter only, never invent times."""
    try:
        did = int(doctor_id or 0)
    except (TypeError, ValueError):
        did = 0
    cands = [s for s in (slots or []) if isinstance(s, dict)
             and (not did or int(s.get("doctor_id") or 0) == did)
             and (not date_iso or str(s.get("starts_at", "")).startswith(date_iso))]
    if not cands:
        return {}
    if start_hr is not None and end_hr is not None:
        try:
            lo, hi = int(start_hr), int(end_hr)
            timed = []
            for s in cands:
                try:
                    from datetime import datetime as _dt
                    hr = _dt.fromisoformat(str(s["starts_at"]).replace("Z", "+00:00")).hour
                    if lo <= hr < hi:
                        timed.append(s)
                except Exception:
                    continue
            if timed:
                return timed[0]
        except (TypeError, ValueError):
            pass
    return cands[0]


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



# ---- backward-compat aliases (orchestration/tests import these from registry) ----
def clean_tokens(text: str) -> list[str]:
    from app.services.guards import clean_tokens as _c
    return _c(text)


def token_match(hay: str, needle: str) -> bool:
    from app.services.guards import token_match as _m
    return _m(hay, needle)


def resolve_doctor_id(db, *, doctor_name: str = "", hospital_id: int = 0, limit: int = 200) -> int:
    from app.services.guards import resolve_doctor_id as _r
    return _r(db, doctor_name=doctor_name, hospital_id=hospital_id, limit=limit)


def pick_verified_slot(slots: list, *, doctor_id: int = 0, date_iso: str = "", start_hr=None, end_hr=None) -> dict:
    from app.services.guards import pick_verified_slot as _p
    return _p(slots, doctor_id=doctor_id, date_iso=date_iso, start_hr=start_hr, end_hr=end_hr)


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
    from app.services.guards import uid as _u
    return _u(user)


def _scope_check(user, hospital_id=None):
    from app.services.guards import scope_check as _s
    return _s(user, hospital_id)


def _review_avg(db, doctor_id=None, hospital_id=None, target="doctor"):
    from app.services.guards import review_avg as _r
    return _r(db, doctor_id=doctor_id, hospital_id=hospital_id, target=target)


# ---- thin delegates: registry owns contracts, services own logic ----
# Each _IMPL entry is a direct reference or 3-line adapter. No business rules here.

def _tokens(q: str) -> list[str]:
    from app.services.guards import tokens as _t
    return _t(q)


async def _search_hospitals(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import discovery_svc as _d
    return await _d.search_hospitals(db, a, user=user)


async def _search_doctors(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import discovery_svc as _d
    return await _d.search_doctors(db, a, user=user)


async def _get_doctor_details(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import discovery_svc as _d
    return await _d.get_doctor_details(db, a, user=user)


async def _get_hospital_details(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import discovery_svc as _d
    return await _d.get_hospital_details(db, a, user=user)


async def _check_availability(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import discovery_svc as _d
    return await _d.check_availability(db, a, user=user)


async def _lookup_patient(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import questionnaire_svc as _q
    return _q.lookup_patient(db, a, user=user)


def _serialize_appt(db, a):
    from app.services.guards import serialize_appointment as _s
    return _s(db, a)


def _own_appt(db, aid, user):
    from app.services.guards import own_appointment as _o
    return _o(db, aid, user)


async def _get_appointment(db, a, user=None, corr="", idem="", conversation_id=None):
    if not a.get("appointment_id"):
        raise ValueError("appointment_id is required")
    from app.services import appointments_svc as _s
    return _s.get_one(db, a, user=user)


async def _create_appointment(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import appointments_svc as _s
    return await _s.create(db, a, user=user, corr=corr, idem=idem, conversation_id=conversation_id)


async def _reschedule_appointment(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import appointments_svc as _s
    return await _s.reschedule(db, a, user=user, corr=corr)


async def _cancel_appointment(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import appointments_svc as _s
    return await _s.cancel(db, a, user=user, corr=corr)


async def _get_questionnaire(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import questionnaire_svc as _q
    return _q.get_one(db, a, user=user)


async def _submit_questionnaire(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import questionnaire_svc as _q
    return _q.submit(db, a, user=user)


async def _send_notification(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services.guards import uid as _u
    from app.services.helpers import notify as _n
    n = _n(db, a.get("kind", "ai_message"), a.get("title", "Update"),
           a.get("body", ""), _u(user), a.get("hospital_id"), "ai", conversation_id)
    return {"id": n.id if n else None, "status": "sent" if n else "failed"}


async def _start_workflow(db, a, user=None, corr="", idem="", conversation_id=None):
    if not a.get("event"):
        raise ValueError("event is required")
    from app.services.workflows import fire_event as _f
    hid = a.get("hospital_id") or getattr(user, "hospital_id", None)
    _f(db, a["event"], hid, {"conversation_id": conversation_id, **(a.get("payload") or {})}, corr)
    return {"event": a["event"], "fired": True}


async def _get_context(db, a, user=None, corr="", idem="", conversation_id=None):
    cid = a.get("conversation_id") or conversation_id
    if not cid:
        raise ValueError("conversation_id is required")
    from app import models as _m
    ctx = db.query(_m.AIContext).filter(_m.AIContext.conversation_id == int(cid)).first()
    if not ctx:
        return {"conversation_id": cid, "slices": {}}
    return {"conversation_id": cid, "slices": {
        "conversational": ctx.conversational, "transactional": ctx.transactional,
        "user_ctx": ctx.user_ctx, "workflow_state": ctx.workflow_state}}


async def _update_preferences(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import profile_svc as _p
    return _p.update_prefs(db, a, user=user)


async def _transfer_to_human(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services.guards import own_appointment as _o
    from app.services.helpers import ops as _ops
    ap = None
    if a.get("appointment_id"):
        try:
            ap = _o(db, a["appointment_id"], user)
        except Exception:
            ap = None
    hid = (ap.hospital_id if ap else None) or getattr(user, "hospital_id", None)
    _ops(db, "human.escalation", f"Escalated conv {conversation_id}: {a.get('summary', '')[:200]}",
         "warn", hid, corr, {"reason": a.get("reason", "human_escalation")})
    return {"escalated": True, "queue": "care_team"}


async def _get_reviews(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import reviews_svc as _r
    return _r.list_reviews(db, a, user=user)


async def _list_my_appointments(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import appointments_svc as _s
    return _s.list_mine(db, a, user=user)


async def _list_my_questionnaires(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import profile_svc as _p
    return _p.list_my_questionnaires(db, a, user=user)


async def _get_notifications(db, a, user=None, corr="", idem="", conversation_id=None):
    from app.services import profile_svc as _p
    return _p.get_notifications(db, a, user=user)


# ---- generic patient tools: config only, executors live in services ----
_GENERIC_DEFS: dict[str, dict] = {
    "find_next_available": {"svc": "discovery_svc", "fn": "find_next_available"},
    "get_hospital_info": {"svc": "discovery_svc", "fn": "get_hospital_info"},
    "list_specialties": {"svc": "discovery_svc", "fn": "taxonomy_list"},
    "list_departments": {"svc": "discovery_svc", "fn": "taxonomy_list"},
    "list_appointment_types": {"svc": "discovery_svc", "fn": "taxonomy_list"},
    "list_questionnaires": {"svc": "discovery_svc", "fn": "taxonomy_list"},
    "get_appointment_details": {"svc": "appointments_svc", "fn": "get_details"},
    "submit_review": {"svc": "reviews_svc", "fn": "create_review"},
    "get_my_profile": {"svc": "profile_svc", "fn": "get_my_profile"},
    "update_my_profile": {"svc": "profile_svc", "fn": "update_my_profile"},
    "get_my_dashboard": {"svc": "profile_svc", "fn": "get_my_dashboard"},
}


def _make_generic(tool: str):
    """One shared closure per new tool — no per-tool bodies."""
    cfg = _GENERIC_DEFS[tool]

    async def _fn(db, a, user=None, corr="", idem="", conversation_id=None):
        import importlib as _il
        mod = _il.import_module(f"app.services.{cfg['svc']}")
        fn = getattr(mod, cfg["fn"])
        if cfg["fn"] == "taxonomy_list":
            return await fn(db, a or {}, tool, user=user)
        import inspect as _ins
        if _ins.iscoroutinefunction(fn):
            try:
                return await fn(db, a or {}, user=user)
            except TypeError:
                return await fn(db, a or {}, user=user, corr=corr)
        try:
            return fn(db, a or {}, user=user)
        except TypeError:
            return fn(db, a or {}, user=user, corr=corr)

    _fn.__name__ = f"_generic_{tool}"
    return _fn


_IMPL = {
    "search_hospitals": _search_hospitals, "search_doctors": _search_doctors,
    "get_doctor_details": _get_doctor_details, "get_hospital_details": _get_hospital_details,
    "check_availability": _check_availability, "lookup_patient": _lookup_patient,
    "get_appointment": _get_appointment, "create_appointment": _create_appointment,
    "reschedule_appointment": _reschedule_appointment, "cancel_appointment": _cancel_appointment,
    "get_questionnaire": _get_questionnaire, "submit_questionnaire": _submit_questionnaire,
    "send_notification": _send_notification, "start_workflow": _start_workflow,
    "get_context": _get_context, "update_preferences": _update_preferences,
    "transfer_to_human": _transfer_to_human, "get_reviews": _get_reviews,
    "list_my_appointments": _list_my_appointments, "list_my_questionnaires": _list_my_questionnaires,
    "get_notifications": _get_notifications,
}
for _t in _GENERIC_DEFS:
    _IMPL[_t] = _make_generic(_t)
