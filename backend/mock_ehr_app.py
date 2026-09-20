"""Mock EHR vendored for single-server Render deploy.

Same code as ../mock-ehr/app.py (module renamed so it can live next to
the backend app in one image). Local docker-compose still uses the
standalone mock-ehr/ service; Render single-server runs this module on
127.0.0.1:8001 inside the backend container via start_combined.sh.
"""
import time
import uuid

from fastapi import FastAPI, Header, HTTPException, Request
from pydantic import BaseModel

app = FastAPI(title="Mock EHR", version="1.0.0")
API_KEY = "mock-ehr-dev-key"
store = {"appointments": {}, "by_idem": {}, "patients": {}, "providers": {}}

# pre-seed providers/patients
for i, n in enumerate(["Maya Rao", "James Lee", "Sara Khan", "Tom Becker"]):
    store["providers"][f"ext-prov-{i}"] = {"id": f"ext-prov-{i}", "name": f"Dr. {n}", "specialty": ["Orthopedics", "Cardiology", "Dermatology", "General Medicine"][i]}
for i, n in enumerate(["Aarav Sharma", "Emily Chen", "John Carter"]):
    store["patients"][f"ext-pat-{i}"] = {"id": f"ext-pat-{i}", "name": n}


def _auth(x_api_key: str | None):
    import os

    if (x_api_key or "") != os.getenv("MOCK_EHR_API_KEY", API_KEY):
        raise HTTPException(401, "bad ehr key")


class ApptIn(BaseModel):
    patient_ref: str = ""
    patient_name: str = ""
    provider_id: str = ""
    facility_id: str = ""
    starts_at: str = ""
    ends_at: str = ""
    reason: str = ""
    idempotency_key: str = ""


@app.get("/health")
def health():
    return {"ok": True, "service": "mock-ehr", "appointments": len(store["appointments"])}


@app.get("/ehr/patients")
def patients(q: str = "", x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    return [p for p in store["patients"].values() if not q or q.lower() in p["name"].lower()]


@app.get("/ehr/providers")
def providers(q: str = "", x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    return [p for p in store["providers"].values() if not q or q.lower() in p["name"].lower()]


@app.get("/ehr/appointments")
def list_appts(idempotency_key: str = "", x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    if idempotency_key:
        hit = store["by_idem"].get(idempotency_key)
        return [hit] if hit else []
    return list(store["appointments"].values())[-50:]


@app.post("/ehr/appointments")
def create(a: ApptIn, request: Request, x_api_key: str | None = Header(default=None), idempotency_key: str | None = Header(default=None)):
    _auth(x_api_key)
    if request.query_params.get("fail") == "timeout":
        time.sleep(0.2)
        raise HTTPException(504, "simulated timeout")
    key = idempotency_key or a.idempotency_key
    if key and key in store["by_idem"]:
        return store["by_idem"][key]  # idempotent replay
    # slot conflict on same provider+start
    for ex in store["appointments"].values():
        if ex["provider_id"] == a.provider_id and ex["starts_at"] == a.starts_at and ex["status"] != "cancelled":
            raise HTTPException(409, "slot conflict in EHR")
    eid = f"ext-appt-{uuid.uuid4().hex[:8]}"
    rec = {"id": eid, "patient_ref": a.patient_ref, "patient_name": a.patient_name, "provider_id": a.provider_id, "facility_id": a.facility_id, "starts_at": a.starts_at, "ends_at": a.ends_at, "reason": a.reason, "status": "booked", "idempotency_key": key}
    store["appointments"][eid] = rec
    if key:
        store["by_idem"][key] = rec
    return rec


@app.get("/ehr/appointments/{eid}")
def get_one(eid: str, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    if eid not in store["appointments"]:
        raise HTTPException(404, "not found")
    return store["appointments"][eid]


@app.patch("/ehr/appointments/{eid}")
def update(eid: str, patch: dict, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    if eid not in store["appointments"]:
        raise HTTPException(404, "not found")
    store["appointments"][eid].update({k: v for k, v in patch.items() if k in ("starts_at", "ends_at", "status", "reason")})
    return store["appointments"][eid]


@app.delete("/ehr/appointments/{eid}")
def cancel(eid: str, x_api_key: str | None = Header(default=None)):
    _auth(x_api_key)
    if eid not in store["appointments"]:
        raise HTTPException(404, "not found")
    store["appointments"][eid]["status"] = "cancelled"
    return {"id": eid, "status": "cancelled"}
