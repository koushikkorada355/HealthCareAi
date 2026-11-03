"""Shared guards + serialization for REST controllers and MCP tools.

Single source of truth for tenant isolation, ownership, and display shapes.
Both `api/v1/*` and `ai_assistant/mcp/registry` must import from here —
never re-implement these checks.
"""
from __future__ import annotations


def uid(user) -> int | None:
    return getattr(user, "id", None)


def scope_check(user, hospital_id=None):
    if (user and getattr(user, "role", "") in ("hospital_admin", "doctor")
            and hospital_id and getattr(user, "hospital_id", None)
            and int(hospital_id) != int(user.hospital_id)):
        raise PermissionError("Cross-tenant denied")


def own_appointment(db, aid, user):
    from app import models
    a = db.query(models.Appointment).filter(
        models.Appointment.id == int(aid)).first()
    if not a:
        raise ValueError("Appointment not found")
    if user and getattr(user, "role", "") == "patient" and a.patient_id != user.patient_id:
        raise PermissionError("Not your appointment")
    if user and getattr(user, "role", "") == "doctor" and a.doctor_id != user.doctor_id:
        raise PermissionError("Not your appointment")
    scope_check(user, a.hospital_id)
    return a


def review_avg(db, doctor_id=None, hospital_id=None, target="doctor"):
    from sqlalchemy import func as _f
    from app import models
    q = db.query(_f.count(models.Review.id), _f.avg(models.Review.rating)).filter(
        models.Review.status == "approved")
    if target == "doctor" and doctor_id:
        q = q.filter(models.Review.doctor_id == doctor_id)
    elif hospital_id:
        q = q.filter(models.Review.hospital_id == hospital_id)
    n, avg = q.first() or (0, None)
    return int(n or 0), round(float(avg or 0), 2)


def jload(raw, default):
    import json as _j
    try:
        v = _j.loads(raw or "")
        return v if isinstance(v, default.__class__) or default is None else default
    except Exception:
        return default


def tokens(q: str) -> list[str]:
    return [t.strip(".,").lower() for t in str(q or "").split() if len(t.strip("., ")) >= 2]


def clean_tokens(text: str) -> list[str]:
    parts = str(text or "").lower().split()
    out = []
    for i, p in enumerate(parts):
        qq = p.strip(".,;:!?\"'()[]")
        if not qq:
            continue
        if i == 0 and p.endswith(".") and len(qq) <= 4:
            continue
        out.append(qq)
    return out


def token_match(hay: str, needle: str) -> bool:
    hay_l = f" {(hay or '').lower()} "
    toks = clean_tokens(needle)
    return bool(toks) and all(t in hay_l for t in toks)


def resolve_doctor_id(db, *, doctor_name: str = "", hospital_id: int = 0,
                      limit: int = 200) -> int:
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


def serialize_appointment(db, a):
    from app import models
    d = db.query(models.Doctor).filter(models.Doctor.id == a.doctor_id).first()
    h = db.query(models.Hospital).filter(models.Hospital.id == a.hospital_id).first()
    return {"id": a.id, "status": a.status, "starts_at": a.starts_at.isoformat(),
            "ends_at": a.ends_at.isoformat(), "mode": a.mode,
            "doctor_id": a.doctor_id, "doctor_name": d.name if d else "",
            "hospital_id": a.hospital_id, "hospital_name": h.name if h else "",
            "correlation_id": a.correlation_id}
