from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from datetime import datetime
from ...db.session import get_db
from ...core.deps import get_current_user
from ...core.correlation import new_corr
from ... import models
from ...ai.graph import run_graph, formulate_reply
from ...mcp.registry import invoke
import json

router = APIRouter(tags=["ai"])

@router.post("/ai/chat")
async def chat(body: dict, db: Session = Depends(get_db), u=Depends(get_current_user)):
    text = (body.get("message") or "").strip()
    corr = body.get("correlation_id") or new_corr()
    conv_id = body.get("conversation_id")
    conv = db.query(models.AIConversation).filter(models.AIConversation.id==conv_id).first() if conv_id else None
    if not conv:
        conv = models.AIConversation(user_id=u.id, hospital_id=u.hospital_id, channel=body.get("channel","web"), status="active", correlation_id=corr)
        db.add(conv); db.commit(); db.refresh(conv)
        db.add(models.AIContext(conversation_id=conv.id)); db.commit()
    ctx = db.query(models.AIContext).filter(models.AIContext.conversation_id==conv.id).first()
    prior = {}
    try: prior = json.loads(ctx.conversational or "{}")
    except Exception: prior = {}
    # safety: refuse clinical
    from ...ai.safety import check_admin_only
    ok, note = check_admin_only(text)
    db.add(models.AIMessage(conversation_id=conv.id, role="user", content=text)); db.commit()
    g = run_graph(text, prior)
    trace = [f"intent={g.get('intent')}", f"route={g.get('route')}"]
    reply_extra = {}
    powered_by = "rules"
    if not ok:
        reply = note
    elif g.get("route") == "clarify":
        reply, used = await formulate_reply(g)
        powered_by = "grok" if used else "rules"
    elif g.get("intent") == "greeting":
        reply, used = await formulate_reply(g)
        powered_by = "grok" if used else "rules"
    elif g.get("route") == "discover":
        spec = g.get("specialty","")
        try:
            r = await invoke(db, "search_doctors", {"specialty": spec}, user=u, conversation_id=conv.id, corr=corr)
            docs = r["data"]["doctors"][:5]
            trace.append(f"search_doctors specialty={spec} -> {len(docs)}")
            if not docs:
                reply = f"I couldn't find an active {spec or ''} doctor right now. Want to try another specialty or hospital?"
            else:
                # attach real availability for first doctor
                try:
                    av = await invoke(db, "check_availability", {"doctor_id": docs[0]["id"], "days_ahead": 7}, user=u, conversation_id=conv.id, corr=corr)
                    slots = av["data"]["slots"][:6]
                    trace.append(f"check_availability doctor={docs[0]['id']} -> {len(slots)} slots")
                except Exception: slots = []
                prior.update({"specialty": spec, "doctor_id": docs[0]["id"]})
                lines = [f"**{d['name']}** ({d['specialty'] or spec}) — {d['hospital_id']}" for d in docs]
                slot_lines = "\n".join(f"- {s['starts_at'][:16].replace('T',' ')} (slot, calendar {s['calendar_id']})" for s in slots) or "- checking calendar…"
                base = f"Here are real options for **{spec or 'care'}**:\n" + "\n".join("• "+l for l in lines) + f"\n\nEarliest real availability with {docs[0]['name']}:\n{slot_lines}\n\nTell me a slot (e.g. 'book Thursday 10:00 with {docs[0]['name']}') and I'll verify + confirm."
                reply, used = await formulate_reply(g, {"message": base})
                powered_by = "grok" if used else "rules"
                reply_extra = {"doctors": docs, "slots": slots}
        except Exception as e:
            reply = f"Search hit an issue ({str(e)[:120]}). Want me to escalate to a human?"
    elif g.get("route") == "discover_hospitals":
        import re
        tl = text.lower()
        city = (prior.get("city") or "").strip()
        try:
            cities = [r[0] for r in db.query(models.Hospital.city).filter(models.Hospital.status == "approved").distinct().all() if r[0]]
        except Exception:
            cities = []
        if not city:
            for c in cities:
                if c and c.lower() in tl:
                    city = c
                    break
        if not city:
            m = re.search(r"\bin\s+([a-zA-Z][a-zA-Z\s-]{1,40})", tl)
            if m:
                city = m.group(1).strip().title()
        if not city:
            chips = ", ".join(cities[:6]) or "your city"
            reply = f"Which city should I search? e.g. {chips} — or say 'anywhere'."
            reply_extra = {"cities": cities[:10], "needs_city": True}
            trace.append("search_hospitals skipped: needs city")
        else:
            try:
                r = await invoke(db, "search_hospitals", {"city": city} if city.lower() != "anywhere" else {}, user=u, conversation_id=conv.id, corr=corr)
                hs = r["data"]["hospitals"][:8]
                trace.append(f"search_hospitals city={city} -> {len(hs)}")
                prior["city"] = city
                if not hs:
                    reply = f"I couldn't find an approved hospital in {city} right now. Want to try another city ({', '.join(cities[:6]) or 'nearby'})?"
                else:
                    lines = [f"**{h['name']}** — {h.get('city','')}" for h in hs]
                    base = f"Here are approved hospitals in **{city}**:\n" + "\n".join("• " + l for l in lines) + "\n\nTell me a hospital to see its doctors, or say another city."
                    reply, used = await formulate_reply(g, {"message": base})
                    powered_by = "grok" if used else "rules"
                    reply_extra = {"hospitals": hs, "city": city}
            except Exception as e:
                reply = f"Search hit an issue ({str(e)[:120]}). Want me to escalate to a human?"
    elif g.get("route") == "profile":
        tl = text.lower()
        try:
            if any(w in tl for w in ["hospital", "clinic", "citycare", "riverside", "northgate"]):
                name_hint = tl.replace("tell me about", "").replace("who is", "").replace("best", "").strip(" ?.,") or ""
                if not name_hint and not prior.get("hospital_id"):
                    reply = "Which hospital? e.g. 'tell me about CityCare General' — or say a city for nearby options."
                else:
                    r = await invoke(db, "get_hospital_details", {"name": name_hint} if name_hint else {"hospital_id": prior["hospital_id"]}, user=u, conversation_id=conv.id, corr=corr)
                    h = r["data"]
                    trace.append(f"get_hospital_details -> {h.get('name')}")
                    if prior.get("hospital_id") is None:
                        prior["hospital_id"] = h.get("id")
                    docs = "; ".join(f"{x['name']} ({x.get('specialty','')})" for x in (h.get("doctors") or [])[:4]) or "roster updating"
                    base = (f"**{h.get('name')}** — {h.get('city','')} · {h.get('address','')}\n"
                            f"Doctors: {h.get('doctor_count',0)} active ({docs})\n"
                            f"Services: {h.get('services','')} · Completed visits: {h.get('completed_visits',0)}\n"
                            f"Rating: {h.get('avg_rating',0)} ({h.get('review_count',0)} reviews) — {h.get('reviews_summary','')}\n\n"
                            f"Want doctors, slots, or another hospital?")
                    reply, used = await formulate_reply(g, {"message": base})
                    powered_by = "grok" if used else "rules"
                    reply_extra = {"hospital": h}
            else:
                spec = g.get("specialty") or ""
                name_hint = tl.replace("tell me about", "").replace("who is", "").replace("dr.", "dr ").replace("best", "").strip()
                if not spec and not any(len(w) > 2 for w in name_hint.split()):
                    reply = "Which doctor? Tell me a name (e.g. 'tell me about Dr Maya Rao') or specialty + city (e.g. 'best cardiologist in Springfield')."
                else:
                    try:
                        r = await invoke(db, "search_doctors", {"specialty": spec, "q": name_hint[:40] if name_hint else ""}, user=u, conversation_id=conv.id, corr=corr)
                        ds = r["data"]["doctors"][:3]
                        trace.append(f"search_doctors profile spec={spec} -> {len(ds)}")
                    except Exception:
                        ds = []
                    if not ds:
                        reply = "I couldn't find that doctor among active doctors. Try a name or specialty + city."
                    else:
                        d = ds[0]
                        try:
                            det = await invoke(db, "get_doctor_details", {"doctor_id": d["id"]}, user=u, conversation_id=conv.id, corr=corr)
                            dd = det["data"]
                            trace.append(f"get_doctor_details doctor={d['id']}")
                        except Exception:
                            dd = d
                        prior["doctor_id"] = dd.get("id")
                        slots = "; ".join(s["starts_at"][:16].replace("T", " ") for s in (dd.get("next_slots") or [])[:3]) or "checking calendar"
                        rev = dd.get("reviews_summary") or "No patient reviews yet."
                        base = (f"**{dd.get('name')}** — {dd.get('specialty','')} · {dd.get('experience_years',0)}y exp · ★ {dd.get('rating',0)}\n"
                                f"{dd.get('hospital_name','')} ({dd.get('hospital_city','')}) · {dd.get('qualifications','')}\n"
                                f"Languages: {dd.get('languages','')} · Completed visits: {dd.get('completed_visits',0)}\n"
                                f"Next slots: {slots}\nRating: {dd.get('avg_rating',0)} ({dd.get('review_count',0)} reviews) — {rev}\n\n"
                                f"Want slots, booking, or another doctor?")
                        reply, used = await formulate_reply(g, {"message": base})
                        powered_by = "grok" if used else "rules"
                        reply_extra = {"doctor": dd}
        except Exception as e:
            reply = f"Lookup hit an issue ({str(e)[:120]}). Want me to escalate to a human?"
    elif g.get("intent") in ("book",) and g.get("route") == "discover":
        reply, used = await formulate_reply(g)
        powered_by = "grok" if used else "rules"
    else:
        # booking attempt: parse "book ... <iso or 15:00>" — simplest: if slots in prior + time mentioned, book first slot
        reply = "To book, pick a doctor and slot from above (or go to Find doctors → pick a real slot). I only book verified availability."
    # persist conversational slice (no sensitive bulk)
    try:
        prior["intent"] = g.get("intent"); prior["specialty"] = g.get("specialty") or prior.get("specialty")
        ctx.conversational = json.dumps({k: prior.get(k) for k in ("intent", "specialty", "city", "hospital_id", "doctor_id", "date_pref") if prior.get(k) is not None}); db.commit()
    except Exception: pass
    db.add(models.AIMessage(conversation_id=conv.id, role="assistant", content=reply)); db.commit()
    return {"conversation_id": conv.id, "correlation_id": corr, "intent": g.get("intent"), "route": g.get("route"), "reply": reply, "trace": trace, "data": reply_extra, "powered_by": powered_by}

@router.get("/ai/status")
def ai_status(u=Depends(get_current_user)):
    """What powers AI wording right now. Never exposes the key — only whether one is set."""
    import os
    from ...ai.grok_client import grok_configured, grok_model
    return {
        "grok_configured": grok_configured(),
        "grok_model": grok_model(),
        "powered_by_default": "grok" if grok_configured() else "rules",
        "stt_provider": os.getenv("VOICE_STT_PROVIDER", "browser"),
        "tts_provider": os.getenv("VOICE_TTS_PROVIDER", "browser"),
        "note": "Add GROK_API_KEY to .env and restart the backend to enable Grok wording.",
    }

@router.get("/ai/conversations")
def convs(db: Session = Depends(get_db), u=Depends(get_current_user)):
    q = db.query(models.AIConversation)
    if u.role == "patient": q = q.filter(models.AIConversation.user_id==u.id)
    elif u.role in ("hospital_admin","doctor") and u.hospital_id: q = q.filter(models.AIConversation.hospital_id==u.hospital_id)
    out = []
    for c in q.order_by(models.AIConversation.updated_at.desc()).limit(100).all():
        n = db.query(models.AIMessage).filter(models.AIMessage.conversation_id==c.id).count()
        out.append({"id":c.id,"channel":c.channel,"status":c.status,"correlation_id":c.correlation_id,"messages":n,"updated_at":c.updated_at.isoformat()})
    return out

@router.get("/ai/conversations/{cid}")
def conv_detail(cid: int, db: Session = Depends(get_db), u=Depends(get_current_user)):
    msgs = [{"role":m.role,"content":m.content,"at":m.created_at.isoformat()} for m in db.query(models.AIMessage).filter(models.AIMessage.conversation_id==cid).order_by(models.AIMessage.id).all()]
    caps = [{"name":c.name,"status":c.status,"at":c.created_at.isoformat(),"correlation_id":c.correlation_id} for c in db.query(models.CapabilityExecution).filter(models.CapabilityExecution.conversation_id==cid).order_by(models.CapabilityExecution.id.desc()).limit(50).all()]
    return {"messages": msgs, "capabilities": caps}
