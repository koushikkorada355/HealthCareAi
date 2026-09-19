"""Repeatable seed + idempotent top-up: hospitals, doctors (photos), calendars,
patients, past+future appointments, questionnaires, AI, integrations, workflows.

`run()` is safe to execute on every boot: the full seed runs once, then
`topup()` patches older databases (photo URLs, future appointments, evals)
without duplicating anything (idempotency keys + existence checks)."""
import json, random
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import Session
from ..core.security import hash_password
from .. import models

def _u(db, email, role, name, **kw):
    u = db.query(models.User).filter(models.User.email==email).first()
    if u: return u
    u = models.User(email=email, password_hash=hash_password("password123"), role=role, full_name=name, **kw)
    db.add(u); db.commit(); db.refresh(u); return u

def _img(pid):
    return f"https://images.unsplash.com/{pid}?auto=format&fit=crop&w=256&q=60"

# Central Unsplash lists (single source: app/utils/photos.py). Kept here for compat.
try:
    from ..utils.photos import DOCTOR_PHOTOS, HOSPITAL_COVERS, hospital_cover_for
except Exception:
    DOCTOR_PHOTOS = [
        _img("photo-1559839734-2b71ea197ec2"),
        _img("photo-1612349317150-e413f6a5b16d"),
        _img("photo-1594824476967-48c8b964273f"),
        _img("photo-1622253692010-333f2da6031d"),
        _img("photo-1651008376811-b90baee60c1f"),
        _img("photo-1582750433449-648ed127bb54"),
        _img("photo-1638202993928-7267aad84c31"),
        _img("photo-1537368910025-700350fe46c7"),
        _img("photo-1551601651-2a8555f1a136"),
        _img("photo-1579684385127-1ef15d508118"),
        _img("photo-1612349316228-5942a9b489c2"),
        _img("photo-1580489944761-15a19d654956"),
    ]
    HOSPITAL_COVERS = []
    def hospital_cover_for(slug: str) -> str:
        return ""

def topup(db: Session):
    """Patch existing databases: photos, future visits, evals, demo Q response."""
    docs = db.query(models.Doctor).order_by(models.Doctor.id).all()
    for i, d in enumerate(docs):
        if not d.photo_url:
            d.photo_url = DOCTOR_PHOTOS[i % len(DOCTOR_PHOTOS)]
    # Backfill hospital covers (auto-Unsplash, no prompt). Skip if column missing on old DBs.
    try:
        for h in db.query(models.Hospital).all():
            if not getattr(h, "cover_url", None):
                h.cover_url = hospital_cover_for(h.slug)
    except Exception:
        pass
    db.commit()
    now = datetime.now(timezone.utc)
    pats = db.query(models.Patient).order_by(models.Patient.id).all()
    # future confirmed visits so Upcoming/doctor-today views are alive
    if docs and pats:
        for i in range(4):
            key = f"seed-future-{i}"
            if db.query(models.Appointment).filter(models.Appointment.idempotency_key==key).first(): continue
            d = docs[i % len(docs)]; p = pats[(i + 1) % len(pats)]
            day = now + timedelta(days=i + 1)
            while day.weekday() > 4: day += timedelta(days=1)
            st0 = day.replace(hour=10 + (i % 4), minute=0, second=0, microsecond=0)
            # never collide with seeded lunch block (12:00 day+2)
            a = models.Appointment(hospital_id=d.hospital_id, doctor_id=d.id, patient_id=p.id,
                starts_at=st0, ends_at=st0 + timedelta(minutes=30), status="confirmed",
                reason="Follow-up visit", idempotency_key=key, correlation_id=f"seedf{i}",
                external_appointment_id=f"ext-appt-future-{i}", integration_status="synced")
            db.add(a); db.commit()
            db.add(models.AppointmentHistory(appointment_id=a.id, from_status="requested", to_status="confirmed", actor="seed", correlation_id=f"seedf{i}")); db.commit()
    # one completed questionnaire response for doctor review demo
    if db.query(models.QuestionnaireResponse).count() == 0:
        q = db.query(models.Questionnaire).first()
        ap = db.query(models.Appointment).first()
        if q and ap:
            db.add(models.QuestionnaireResponse(questionnaire_id=q.id, appointment_id=ap.id, patient_id=ap.patient_id,
                answers_json=json.dumps({"reason": "Shoulder pain for 3 weeks", "pain_level": 6, "first_visit": "yes", "allergies": "None"}),
                status="completed", collected_via="ai_chat")); db.commit()
    # AI evaluation samples
    if db.query(models.AIEvaluation).count() == 0:
        for m, s in [("intent_accuracy", 0.94), ("clarification_rate", 0.88), ("tool_success", 0.97), ("safety_refusal", 1.0)]:
            db.add(models.AIEvaluation(metric=m, score=s, detail=json.dumps({"window": "7d"})))
        db.commit()
    _seed_demo_applications(db)
    return {"topup": True}

DEMO_APPLICATIONS = [
    # name, slug, status, address, city, review_note
    ("GreenValley Medical Center", "greenvalley-medical", "submitted", "14 Green Valley Rd, Springfield", "Springfield", ""),
    ("Lakeside Health Clinic", "lakeside-health", "corrections_requested", "22 Lake View Dr, Lakeside", "Lakeside", "Please upload fire NOC and license copy, then resubmit."),
    ("Sunrise Rural Hospital", "sunrise-rural", "draft", "9 Sunrise Lane, Northgate", "Northgate", ""),
    ("Metro Surgical Institute", "metro-surgical", "rejected", "101 Metro Ave, Springfield", "Springfield", "Service area overlaps an existing approved hospital."),
    ("Harborview Medical Center", "harborview-medical", "suspended", "77 Harbor Rd, Lakeside", "Lakeside", "Suspended pending license re-verification."),
]

def _seed_demo_applications(db: Session):
    """Demo review queue: one application per lifecycle status (idempotent).

    Gives the System Admin something to see in Applications/Dashboard
    right after a fresh boot. Skips any slug that already exists.
    """
    for name, slug, status, addr, city, note in DEMO_APPLICATIONS:
        if db.query(models.Hospital).filter(models.Hospital.slug == slug).first():
            continue
        h = models.Hospital(
            name=name, slug=slug, status=status, address=addr, city=city,
            phone="+1-555-0142", contact_email=f"admin@{slug}.org",
            operating_hours=json.dumps({"mon": [["09:00", "17:00"]], "tue": [["09:00", "17:00"]], "wed": [["09:00", "17:00"]], "thu": [["09:00", "17:00"]], "fri": [["09:00", "15:00"]]}),
            services=json.dumps(["outpatient", "lab"]), ehr_vendor="mock",
            cover_url=hospital_cover_for(slug), review_notes=note,
            external_facility_id=f"ext-fac-{slug}",
        )
        db.add(h); db.commit(); db.refresh(h)
        email = f"admin@{slug}.org"
        u = db.query(models.User).filter(models.User.email == email).first()
        if not u:
            u = models.User(email=email, password_hash=hash_password("password123"), role="hospital_admin", full_name=f"{name} Admin", hospital_id=h.id)
            db.add(u); db.commit(); db.refresh(u)
        else:
            u.hospital_id = h.id; db.commit()
        db.add(models.AuditEvent(actor_user_id=u.id, action="hospital.apply", entity_type="hospital", entity_id=h.id, hospital_id=h.id, detail=json.dumps({"name": name}), correlation_id=f"demo-{slug}")); db.commit()
        if status != "submitted" and status != "draft":
            action = {"under_review": "hospital.under_review", "corrections_requested": "hospital.corrections", "rejected": "hospital.reject", "suspended": "hospital.suspend"}.get(status, f"hospital.{status}")
            db.add(models.AuditEvent(actor_user_id=None, action=action, entity_type="hospital", entity_id=h.id, hospital_id=h.id, detail=json.dumps({"note": note}), correlation_id=f"demo-{slug}")); db.commit()

def run(db: Session):
    if db.query(models.Hospital).count() < 3 or db.query(models.Doctor).count() < 6:
        _full_seed(db)
    else:
        print("seed: already populated")
    _ensure_system_admin(db)
    topup(db)
    print("seed: done")
    return {"seeded": True}

def _ensure_system_admin(db: Session):
    """Hardcoded System Admin login: admin@gmail.com / 12345 (demo only).

    Idempotent: creates or repairs the account on every boot so the
    platform always has a working System Admin entry point.
    """
    u = db.query(models.User).filter(models.User.email=="admin@gmail.com").first()
    if not u:
        u = models.User(email="admin@gmail.com", password_hash=hash_password("12345"), role="platform_admin", full_name="System Admin")
        db.add(u); db.commit(); db.refresh(u)
    else:
        u.password_hash = hash_password("12345"); u.role = "platform_admin"
        u.full_name = u.full_name or "System Admin"; u.is_active = True; db.commit()

def _full_seed(db: Session):
    now = datetime.now(timezone.utc)
    for s in ["Orthopedics","Cardiology","Dermatology","Neurology","Pediatrics","General Medicine","Gynecology","Ophthalmology"]:
        if not db.query(models.Specialty).filter(models.Specialty.hospital_id==None, models.Specialty.name==s).first():
            db.add(models.Specialty(hospital_id=None, name=s, description=f"{s} care"))
    db.commit()
    hospitals = [
        ("CityCare General Hospital","citycare-general","approved","12 Health Ave, Springfield","Springfield"),
        ("Riverside Specialty Clinic","riverside-specialty","approved","88 River Rd, Springfield","Springfield"),
        ("Northgate Community Hospital","northgate-community","under_review","5 Northgate Blvd","Northgate"),
    ]
    h_objs = []
    for name, slug, status, addr, city in hospitals:
        h = db.query(models.Hospital).filter(models.Hospital.slug==slug).first()
        hours = json.dumps({"mon":[["09:00","17:00"]],"tue":[["09:00","17:00"]],"wed":[["09:00","17:00"]],"thu":[["09:00","17:00"]],"fri":[["09:00","15:00"]]})
        if not h:
            h = models.Hospital(name=name, slug=slug, status=status, address=addr, city=city, phone="+1-555-0100", contact_email=f"admin@{slug}.org", operating_hours=hours, services=json.dumps(["outpatient","imaging","lab"]), ehr_vendor="mock", cover_url=hospital_cover_for(slug), external_facility_id=f"ext-fac-{slug}")
            db.add(h); db.commit(); db.refresh(h)
        elif not getattr(h, "cover_url", None):
            try:
                h.cover_url = hospital_cover_for(slug); db.commit()
            except Exception:
                pass
        h_objs.append(h)
    _u(db, "admin@platform.org", "platform_admin", "Platform Admin")
    doc_names = [("Dr. Maya Rao","Orthopedics",10),("Dr. James Lee","Cardiology",12),("Dr. Sara Khan","Dermatology",8),("Dr. Tom Becker","General Medicine",15),("Dr. Anita Desai","Pediatrics",9),("Dr. Chris Novak","Neurology",11)]
    for h in h_objs[:2]:
        for d in ["Orthopedics","Cardiology","General"]:
            if not db.query(models.Department).filter(models.Department.hospital_id==h.id, models.Department.name==d).first():
                db.add(models.Department(hospital_id=h.id, name=d))
        db.commit()
        for s in ["Orthopedics","Cardiology","Dermatology","General Medicine","Pediatrics","Neurology"]:
            if not db.query(models.Specialty).filter(models.Specialty.hospital_id==h.id, models.Specialty.name==s).first():
                db.add(models.Specialty(hospital_id=h.id, name=s))
        db.commit()
        _u(db, f"admin@{h.slug}.org", "hospital_admin", f"{h.name} Admin", hospital_id=h.id)
        if not db.query(models.HealthcareConnection).filter(models.HealthcareConnection.hospital_id==h.id).first():
            db.add(models.HealthcareConnection(hospital_id=h.id, vendor="mock", base_url="http://mock-ehr:8001", status="active", config_json="{}"))
        for at, dur in [("General Consultation",30),("Follow-up",15),("Specialist Consultation",45)]:
            if not db.query(models.AppointmentType).filter(models.AppointmentType.hospital_id==h.id, models.AppointmentType.name==at).first():
                db.add(models.AppointmentType(hospital_id=h.id, name=at, duration_minutes=dur))
        db.commit()
        from ..services.workflows import ensure_defaults
        ensure_defaults(db, h.id)
        if not db.query(models.Questionnaire).filter(models.Questionnaire.hospital_id==h.id).first():
            db.add(models.Questionnaire(hospital_id=h.id, title="Pre-visit intake (general)", description="Allergies, meds, reason for visit", category="pre_visit",
                schema_json=json.dumps([{"id":"allergies","label":"Any known allergies?","type":"short_text","required":False},{"id":"medications","label":"Current medications (list)","type":"long_text","required":False},{"id":"reason","label":"Reason for visit","type":"long_text","required":True},{"id":"pain_level","label":"Pain level 0-10","type":"numeric","required":False},{"id":"first_visit","label":"Is this your first visit?","type":"yes_no","required":True}])))
            db.add(models.Questionnaire(hospital_id=h.id, title="Orthopedics pre-visit", description="Joint/muscle intake", category="ortho",
                schema_json=json.dumps([{"id":"location","label":"Where is the pain?","type":"choice","options":["shoulder","knee","back","other"],"required":True},{"id":"onset","label":"When did it start?","type":"date","required":False},{"id":"prior_injury","label":"Prior injury to this area?","type":"yes_no","required":True},{"id":"notes","label":"Anything else for the doctor?","type":"long_text","required":False}])))
        db.commit()
    ensure_defaults(db, None); db.commit()
    k = 0
    for h in h_objs[:2]:
        for name, spec, exp in doc_names[:4 if h.slug.startswith("city") else 3]:
            if db.query(models.Doctor).filter(models.Doctor.hospital_id==h.id, models.Doctor.name==name).first(): continue
            sp = db.query(models.Specialty).filter(models.Specialty.hospital_id==h.id, models.Specialty.name==spec).first()
            d = models.Doctor(hospital_id=h.id, name=name, specialty_id=sp.id if sp else None, qualifications=f"MD, {spec}", experience_years=exp, languages=json.dumps(["English","Hindi"] if k % 2 == 0 else ["English"]), consultation_types=json.dumps(["in_person","video"]), duration_minutes=30, status="active", external_provider_id=f"ext-prov-{h.slug}-{k}", rating=round(4.3+random.random()*0.6,1), photo_url=DOCTOR_PHOTOS[k % len(DOCTOR_PHOTOS)])
            db.add(d); db.commit(); db.refresh(d)
            _u(db, f"doc{k}@example.org", "doctor", name, hospital_id=h.id, doctor_id=d.id)
            cal = models.Calendar(hospital_id=h.id, doctor_id=d.id, name="Main", is_active=True, working_hours=json.dumps({"mon":[["09:00","17:00"]],"tue":[["09:00","17:00"]],"wed":[["09:00","17:00"]],"thu":[["09:00","17:00"]],"fri":[["09:00","15:00"]]}))
            db.add(cal); db.commit(); db.refresh(cal)
            for wd in range(5):
                db.add(models.AvailabilityRule(calendar_id=cal.id, weekday=wd, start_time="09:00", end_time="17:00" if wd<4 else "15:00", slot_minutes=30))
            day = (now + timedelta(days=2)).replace(hour=12, minute=0, second=0, microsecond=0)
            db.add(models.BlockedSlot(calendar_id=cal.id, starts_at=day, ends_at=day+timedelta(hours=1), reason="Lunch / admin"))
            if k == 1:
                lv0 = (now + timedelta(days=9)).replace(hour=0, minute=0, second=0, microsecond=0)
                db.add(models.Leave(doctor_id=d.id, starts_at=lv0, ends_at=lv0+timedelta(days=2), reason="Conference"))
            db.commit()
            k += 1
    pats = []
    for i, (nm, em) in enumerate([("Aarav Sharma","aarav@example.org"),("Emily Chen","emily@example.org"),("John Carter","john@example.org"),("Priya Nair","priya@example.org")]):
        p = db.query(models.Patient).filter(models.Patient.email==em).first()
        if not p:
            p = models.Patient(full_name=nm, email=em, phone=f"+1-555-010{i}", external_patient_id=f"ext-pat-{i}", home_hospital_id=h_objs[0].id)
            db.add(p); db.commit(); db.refresh(p)
            _u(db, em, "patient", nm, patient_id=p.id)
            db.add(models.UserContextPref(user_id=db.query(models.User).filter(models.User.email==em).first().id, prefs=json.dumps({"channel":"web","language":"en"})))
            db.commit()
        pats.append(p)
    docs = db.query(models.Doctor).filter(models.Doctor.status=="active").all()
    if docs and pats:
        states = ["confirmed","confirmed","completed","cancelled","rescheduled","confirmed"]
        for i, st in enumerate(states):
            d = docs[i % len(docs)]; p = pats[i % len(pats)]
            st0 = (now + timedelta(days=i-6)).replace(hour=10+(i%5), minute=0, second=0, microsecond=0)
            if db.query(models.Appointment).filter(models.Appointment.idempotency_key==f"seed-{i}").first(): continue
            a = models.Appointment(hospital_id=d.hospital_id, doctor_id=d.id, patient_id=p.id, starts_at=st0, ends_at=st0+timedelta(minutes=30), status=st, reason="Seed visit", idempotency_key=f"seed-{i}", correlation_id=f"seed{i}", external_appointment_id=f"ext-appt-seed-{i}", integration_status="synced")
            db.add(a); db.commit()
            db.add(models.AppointmentHistory(appointment_id=a.id, from_status="requested", to_status=st, actor="seed", correlation_id=f"seed{i}")); db.commit()
        d = docs[0]; p = pats[0]; st0 = (now+timedelta(days=1)).replace(hour=15, minute=0, second=0, microsecond=0)
        if not db.query(models.Appointment).filter(models.Appointment.idempotency_key=="seed-recon").first():
            a = models.Appointment(hospital_id=d.hospital_id, doctor_id=d.id, patient_id=p.id, starts_at=st0, ends_at=st0+timedelta(minutes=30), status="reconciliation_required", reason="Timeout demo", idempotency_key="seed-recon", correlation_id="seedrecon", integration_status="unknown_outcome")
            db.add(a); db.commit()
            db.add(models.ReconciliationRecord(hospital_id=d.hospital_id, appointment_id=a.id, issue="unknown_outcome_not_found", status="open", correlation_id="seedrecon")); db.commit()
            db.add(models.IntegrationOperation(hospital_id=d.hospital_id, kind="create", ref_type="appointment", ref_id=a.id, status="unknown_outcome", error="Simulated timeout", idempotency_key="seed-recon", correlation_id="seedrecon")); db.commit()
    if db.query(models.Notification).count() == 0:
        for i in range(6):
            db.add(models.Notification(hospital_id=h_objs[0].id, kind="appointment_confirmation", title=f"Reminder: visit #{i+1}", body="Your visit is coming up. Reply here if you need to reschedule.", status="sent"))
        db.commit()
    if db.query(models.OperationalEvent).count() == 0:
        for i in range(8):
            db.add(models.OperationalEvent(kind="seed.event", severity="info", message=f"Seed event {i}", correlation_id=f"seed{i}"))
            db.add(models.AuditEvent(action="seed.action", entity_type="appointment", detail="{}", correlation_id=f"seed{i}"))
        db.commit()
    u = db.query(models.User).filter(models.User.email=="aarav@example.org").first()
    if u and not db.query(models.AIConversation).first():
        c = models.AIConversation(user_id=u.id, channel="web", status="active", correlation_id="seedconv1"); db.add(c); db.commit(); db.refresh(c)
        db.add(models.AIMessage(conversation_id=c.id, role="user", content="I need to see a doctor for my shoulder pain sometime this week.")); db.add(models.AIMessage(conversation_id=c.id, role="assistant", content="Found 3 orthopedic options with real availability. Which slot works for you?")); db.commit()
        db.add(models.AIContext(conversation_id=c.id, conversational=json.dumps({"intent":"book","specialty":"Orthopedics"}))); db.commit()
        db.add(models.CapabilityExecution(name="search_doctors", status="success", input_json='{"specialty":"Orthopedics"}', output_json='{"doctors":3}', correlation_id="seedconv1")); db.commit()
