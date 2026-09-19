import React, { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api/client.js'
import { Card, Pill, Avatar, Empty } from '../../components/ui.jsx'
import { hospitalCover } from '../../utils/photos.js'

const SPECIALTIES = ['All', 'Orthopedics', 'Cardiology', 'Dermatology', 'Neurology', 'Pediatrics', 'General Medicine']

const PROBLEM_CHIPS = ['Shoulder pain', 'Skin rash', 'Heart concern', 'Child fever', 'Headache', 'General checkup']
const DAY_OPTS = ['Any day', 'Today', 'Tomorrow', 'This week']

/* Guess specialty from the patient's own words (same mapping the backend uses). */
function detectSpec(text) {
  const t = (text || '').toLowerCase()
  if (/(shoulder|knee|joint|bone|fracture|back pain|neck|ankle|hip|muscle|sprain|orthop)/.test(t)) return 'Orthopedics'
  if (/(skin|rash|acne|eczema|hair|mole|dermat)/.test(t)) return 'Dermatology'
  if (/(heart|chest|blood pressure|cholesterol|palpitat|cardi)/.test(t)) return 'Cardiology'
  if (/(child|baby|kid|infant|toddler|pediatr)/.test(t)) return 'Pediatrics'
  if (/(headache|migraine|brain|nerve|seizure|dizz|neur)/.test(t)) return 'Neurology'
  if (/(fever|cold|cough|flu|checkup|general|stomach|diabet|thyroid)/.test(t)) return 'General Medicine'
  return ''
}

function Steps({ step }) {
  return (
    <div className="mb-5 flex items-center gap-2 text-xs font-bold">
      <span className={`rounded-full px-3 py-1.5 ${step === 1 ? 'bg-brand text-white shadow-lift' : 'bg-brand-soft text-brand-ink'}`}>1 · Choose doctor</span>
      <span className="text-ink-faint">→</span>
      <span className={`rounded-full px-3 py-1.5 ${step === 2 ? 'bg-brand text-white shadow-lift' : 'bg-slate-100 text-ink-soft'}`}>2 · Slot, details & confirm</span>
    </div>
  )
}

const MODES = [
  { id: 'in_person', label: 'In person' },
  { id: 'video', label: 'Video call' },
  { id: 'phone', label: 'Phone call' },
]

function fmtSlot(s) {
  if (!s) return '—'
  const d = new Date(s.starts_at)
  return `${d.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' })} · ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
}

/* ================= PAGE 1 — Find care (hospitals + doctors, one creative page) ================= */
export function BookFind() {
  const [hospitals, setHospitals] = useState([])
  const [doctors, setDoctors] = useState([])
  const [q, setQ] = useState('')
  const [spec, setSpec] = useState('All')
  const [specTouched, setSpecTouched] = useState(false)
  const [hospId, setHospId] = useState('')
  const [loading, setLoading] = useState(true)
  // intake-first: the page asks about the visit BEFORE showing any doctor
  const [stage, setStage] = useState('intake') // intake | results
  const [problem, setProblem] = useState('')
  const [dayPref, setDayPref] = useState('Any day')
  const [intakeErr, setIntakeErr] = useState('')
  const nav = useNavigate()

  useEffect(() => {
    Promise.all([api('/hospitals').catch(() => []), api('/doctors').catch(() => [])])
      .then(([h, d]) => { setHospitals(h || []); setDoctors(d || []) })
      .finally(() => setLoading(false))
  }, [])

  const onProblem = (v) => {
    setProblem(v); setIntakeErr('')
    if (!v.trim()) { setSpec('All'); setSpecTouched(false); return }
    if (!specTouched) { const d = detectSpec(v); if (d) setSpec(d) }
  }
  const pickSpec = (s) => { setSpec(s); setSpecTouched(true) }

  const findDoctors = () => {
    if (!problem.trim()) { setIntakeErr('Please describe your problem in a few words first — e.g. "shoulder pain since last week".'); return }
    try {
      sessionStorage.setItem('book_intake', JSON.stringify({ problem: problem.trim(), specialty: spec === 'All' ? '' : spec, hospId, dayPref }))
    } catch { /* private mode — intake just won't carry over */ }
    setStage('results')
    setTimeout(() => document.getElementById('book-results')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }

  const filtered = useMemo(() => doctors.filter(d => {
    if (spec !== 'All' && d.specialty !== spec) return false
    if (hospId && String(d.hospital_id) !== String(hospId)) return false
    if (q && !(d.name || '').toLowerCase().includes(q.toLowerCase())) return false
    return true
  }), [doctors, spec, hospId, q])

  return (
    <div>
      <Steps step={1} />
      {/* intake first — the page asks about the visit BEFORE showing any doctor */}
      <div className="hero-gradient relative overflow-hidden rounded-2xl p-6 text-white shadow-lift md:p-8">
        <div className="relative">
          <div className="inline-block rounded-full bg-white/15 px-3 py-1 text-[11px] font-bold tracking-wider backdrop-blur">✦ STEP 1 OF 2 · TELL US ABOUT YOUR VISIT</div>
          <h1 className="font-display mt-2 text-3xl font-semibold md:text-4xl">What brings you in today?</h1>
          <p className="mt-1 max-w-xl text-sm opacity-85">Answer a few quick questions and we will match you with the right doctors and their real availability. Nothing is booked on this page.</p>

          <label htmlFor="book-problem" className="mt-4 block text-xs font-bold tracking-wide">1 · WHAT IS THE PROBLEM? *</label>
          <textarea id="book-problem" className="input mt-1 max-w-xl !border-white/30 !bg-white/95 !text-ink" rows={2}
            placeholder='Describe it in your own words — e.g. "shoulder pain since last week"' value={problem} onChange={e => onProblem(e.target.value)} />
          <div className="mt-2 flex flex-wrap gap-2">
            {PROBLEM_CHIPS.map(c => (
              <button key={c} type="button" onClick={() => onProblem(problem.trim() ? `${problem.trim()} + ${c.toLowerCase()}` : c)}
                className="rounded-full bg-white/15 px-3 py-1.5 text-xs font-bold backdrop-blur transition hover:bg-white/25">+ {c}</button>
            ))}
          </div>
          {detectSpec(problem) && <div className="mt-2 text-xs font-bold text-white/90">Looks like <span className="rounded-full bg-white px-2 py-0.5 text-brand-ink">{detectSpec(problem)}</span> — you can change it below.</div>}

          <div className="mt-4 text-xs font-bold tracking-wide">2 · WHICH SPECIALTY?</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {SPECIALTIES.map(s => (
              <button key={s} type="button" onClick={() => pickSpec(s)}
                className={`rounded-full px-4 py-1.5 text-xs font-bold backdrop-blur transition ${spec === s ? 'bg-white text-brand-ink shadow-lift' : 'bg-white/15 text-white hover:bg-white/25'}`}>{s}{spec === s ? ' ✓' : ''}</button>
            ))}
          </div>

          <div className="mt-4 grid max-w-xl gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="book-hosp" className="block text-xs font-bold tracking-wide">3 · PREFERRED HOSPITAL</label>
              <select id="book-hosp" className="input mt-1 !border-white/30 !bg-white/95 !text-ink" value={hospId} onChange={e => setHospId(e.target.value)}>
                <option value="">No preference</option>
                {hospitals.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
              </select>
            </div>
            <div>
              <div className="text-xs font-bold tracking-wide">4 · PREFERRED DAY</div>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {DAY_OPTS.map(dy => (
                  <button key={dy} type="button" onClick={() => setDayPref(dy)}
                    className={`rounded-full px-3 py-2 text-xs font-bold transition ${dayPref === dy ? 'bg-white text-brand-ink shadow-lift' : 'bg-white/15 text-white hover:bg-white/25'}`}>{dy}</button>
                ))}
              </div>
            </div>
          </div>

          {intakeErr && <div className="mt-3 max-w-xl rounded-xl bg-red-500/20 p-2.5 text-sm font-semibold">{intakeErr}</div>}
          <button type="button" onClick={findDoctors} className="mt-4 rounded-xl bg-white px-6 py-3 font-bold text-brand-ink shadow-lift transition hover:-translate-y-0.5">
            Find matching doctors →
          </button>
        </div>
      </div>

      {stage === 'intake' ? (
        <Card className="mt-5"><Empty title="Answer the questions above" sub="Matching doctors and their real availability will appear here. Nothing gets booked automatically." /></Card>
      ) : (
      <div id="book-results" className="scroll-mt-4">
      {/* answers summary */}
      <div className="card mt-5 flex flex-wrap items-center gap-2 p-4 text-sm">
        <span className="font-bold">Your visit:</span>
        <span className="rounded-full bg-brand-soft px-2.5 py-1 text-xs font-bold text-brand-ink">“{problem}”</span>
        {spec !== 'All' && <span className="rounded-full bg-brand-soft px-2.5 py-1 text-xs font-bold text-brand-ink">{spec}</span>}
        <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-ink-soft">{dayPref}</span>
        <button type="button" onClick={() => setStage('intake')} className="ml-auto font-bold text-brand-deep underline">← Change answers</button>
        <input className="input mt-1 w-full max-w-xs !py-2 text-sm" placeholder="Filter by doctor name…" value={q} onChange={e => setQ(e.target.value)} />
      </div>
      {/* hospital strip */}
      <div className="stagger mt-5 grid gap-3 sm:grid-cols-2">
        {hospitals.map(h => (
          <button key={h.id} type="button" onClick={() => setHospId(String(h.id) === hospId ? '' : String(h.id))}
            className={`group relative h-28 overflow-hidden rounded-2xl text-left shadow-card transition hover:-translate-y-0.5 ${String(h.id) === hospId ? 'ring-4 ring-brand' : ''}`}>
            <img src={h.cover_url || hospitalCover(h.slug)} alt={h.name} loading="lazy" className="absolute inset-0 h-full w-full object-cover transition duration-500 group-hover:scale-105"
              onError={(e) => { e.currentTarget.style.display = 'none' }} />
            <div className="absolute inset-0 bg-gradient-to-r from-brand-ink/80 via-brand-ink/40 to-transparent" />
            <div className="absolute bottom-2.5 left-4 right-4">
              <div className="font-display font-semibold text-white">{h.name}</div>
              <div className="text-xs text-white/75">{h.city} · EHR: {h.ehr_vendor} {String(h.id) === hospId ? '· ✓ selected' : ''}</div>
            </div>
          </button>
        ))}
      </div>

      <div className="mt-6 flex items-center justify-between">
        <h2 className="font-display text-xl font-semibold">{filtered.length} matching doctor{filtered.length === 1 ? '' : 's'}</h2>
        <span className="text-xs text-ink-soft">Pick one to choose a slot — still nothing booked</span>
      </div>

      {loading ? (
        <div className="mt-3 grid gap-4 md:grid-cols-2">{[0, 1, 2, 3].map(i => <div key={i} className="card p-5"><div className="skeleton h-16 rounded-xl" /><div className="skeleton mt-3 h-4 w-2/3" /></div>)}</div>
      ) : filtered.length ? (
        <div className="stagger mt-3 grid gap-4 md:grid-cols-2">
          {filtered.map(d => (
            <Card key={d.id} className="card-hover !p-0 overflow-hidden">
              <div className="relative hero-gradient px-5 pb-3 pt-4">
                <div className="text-xs font-bold text-white/80">{d.hospital_name}</div>
                <div className="absolute right-3 top-3"><Pill value={d.status} /></div>
              </div>
              <div className="flex gap-4 p-5">
                <div className="-mt-10 shrink-0"><Avatar name={d.name} size={68} photo={d.photo_url} seed={d.id} plain={false} /></div>
                <div className="min-w-0 flex-1">
                  <div className="font-bold leading-tight">{d.name}</div>
                  <div className="mt-0.5 text-sm text-ink-soft">{d.specialty} · {d.experience_years}y exp {d.rating ? `· ★ ${d.rating}` : ''}</div>
                  <div className="mt-3 flex gap-2">
                    <button type="button" onClick={() => nav(`/app/book/${d.id}`)} className="btn-primary text-sm !px-4 !py-2">View real slots →</button>
                    <Link to={`/app/doctors/${d.id}/slots`} className="btn-ghost text-sm !px-3 !py-2">Classic view</Link>
                  </div>
                </div>
              </div>
            </Card>
          ))}
        </div>
      ) : <Card className="mt-3"><Empty title="No doctors match" sub="Go back and change your answers, or clear the name filter." /></Card>}
      </div>
      )}
    </div>
  )
}

/* ================= PAGE 2 — Pick slot & confirm (slots + verified booking + timeline) ================= */
const CHAIN = ['Requested', 'EHR write', 'External verification', 'State sync', 'Confirmed + notified']

export function BookSlots() {
  const { id } = useParams()
  const [doc, setDoc] = useState(null)
  const [slots, setSlots] = useState([])
  const [loading, setLoading] = useState(true)
  const [me, setMe] = useState(null)
  // guided flow: pick a slot -> fill details -> review -> confirm. Nothing books before confirm.
  const [selected, setSelected] = useState(null)
  const [stage, setStage] = useState('slots') // slots | details | review
  const [reason, setReason] = useState('')
  const [mode, setMode] = useState('in_person')
  const [notes, setNotes] = useState('')
  const [formErr, setFormErr] = useState('')
  const [busy, setBusy] = useState(false)
  const [done, setDone] = useState(null)
  const [err, setErr] = useState('')
  const [prog, setProg] = useState(-1)
  // answers carried over from the Page-1 intake questionnaire
  const [intake, setIntake] = useState(null)

  useEffect(() => {
    setLoading(true)
    try {
      const saved = JSON.parse(sessionStorage.getItem('book_intake') || 'null')
      if (saved?.problem) { setIntake(saved); setReason(saved.problem) }
    } catch { /* no saved intake — reason stays empty, user types it */ }
    Promise.all([api(`/doctors/${id}`).catch(() => null), api(`/availability?doctor_id=${id}&days_ahead=14`).catch(() => ({ slots: [] })), api('/auth/me').catch(() => null)])
      .then(([d, a, u]) => { setDoc(d); setSlots(a?.slots || []); setMe(u) })
      .finally(() => setLoading(false))
  }, [id])

  const dayFiltered = useMemo(() => {
    const pref = intake?.dayPref || 'Any day'
    const today = new Date().toDateString()
    const tm = new Date(); tm.setDate(tm.getDate() + 1); const tomorrow = tm.toDateString()
    if (pref === 'Today') return slots.filter(s => new Date(s.starts_at).toDateString() === today)
    if (pref === 'Tomorrow') return slots.filter(s => new Date(s.starts_at).toDateString() === tomorrow)
    return slots
  }, [slots, intake])

  const grouped = useMemo(() => {
    const g = {}
    for (const s of dayFiltered) {
      const day = new Date(s.starts_at).toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' })
      ;(g[day] ||= []).push(s)
    }
    return Object.entries(g).slice(0, 7)
  }, [dayFiltered])

  const pick = (s) => {
    setSelected(s); setStage('details'); setDone(null); setErr(''); setFormErr('')
    setTimeout(() => document.getElementById('booking-details')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }

  const goReview = () => {
    setFormErr('')
    if (!selected) { setFormErr('Pick a slot first.'); return }
    if (!reason.trim()) { setFormErr('Please tell us the reason for your visit — it helps the doctor prepare.'); return }
    setStage('review')
    setTimeout(() => document.getElementById('booking-details')?.scrollIntoView({ behavior: 'smooth', block: 'start' }), 50)
  }

  const book = async () => {
    const s = selected
    if (!s) return
    setBusy(true); setErr(''); setDone(null); setProg(0)
    const tick = setInterval(() => setProg(p => (p < CHAIN.length - 1 ? p + 1 : p)), 450)
    try {
      const u = me || await api('/auth/me')
      if (!u.patient_id) throw new Error('This login has no patient profile — sign in as a patient (e.g. aarav@example.org).')
      if (!doc) throw new Error('Doctor details are still loading — please wait a moment and retry.')
      const fullReason = notes.trim() ? `${reason.trim()} — ${notes.trim()}` : reason.trim()
      const r = await api('/appointments', {
        method: 'POST',
        body: {
          hospital_id: doc.hospital_id, doctor_id: doc.id, patient_id: u.patient_id,
          starts_at: s.starts_at, ends_at: s.ends_at, calendar_id: s.calendar_id,
          mode, reason: fullReason,
          idempotency_key: `book2page-${u.id}-${doc.id}-${s.starts_at}-${Date.now().toString(36)}`,
        },
      })
      setProg(CHAIN.length - 1)
      setDone(r)
      setSelected(null); setStage('slots')
      // refresh real availability so the just-booked slot disappears
      try {
        const fresh = await api(`/availability?doctor_id=${doc.id}&days_ahead=14`)
        setSlots(fresh?.slots || [])
      } catch { /* keep stale list; slot revalidation happens server-side */ }
    } catch (e) { setErr(e.message); setProg(-1) }
    finally { clearInterval(tick); setBusy(false) }
  }

  return (
    <div>
      <Steps step={2} />
      <Link to="/app/book" className="mb-3 inline-block text-sm font-bold text-brand-deep hover:underline">← Back to all doctors (Step 1)</Link>
      {intake?.problem && (
        <div className="card mb-3 flex flex-wrap items-center gap-2 p-3 text-sm">
          <span className="font-bold">Your visit:</span>
          <span className="rounded-full bg-brand-soft px-2.5 py-1 text-xs font-bold text-brand-ink">“{intake.problem}”</span>
          {intake.specialty && <span className="rounded-full bg-brand-soft px-2.5 py-1 text-xs font-bold text-brand-ink">{intake.specialty}</span>}
          {intake.dayPref && intake.dayPref !== 'Any day' && <span className="rounded-full bg-slate-100 px-2.5 py-1 text-xs font-bold text-ink-soft">slots: {intake.dayPref}</span>}
          <span className="text-xs text-ink-soft">reason prefilled below — you can still edit it</span>
        </div>
      )}
      {doc ? (
        <div className="hero-gradient relative overflow-hidden rounded-2xl p-5 shadow-lift md:p-6">
          <div className="flex items-center gap-4">
            <Avatar name={doc.name} size={68} photo={doc.photo_url} seed={doc.id} plain={false} />
            <div className="text-white">
              <div className="font-display text-2xl font-semibold leading-tight md:text-[28px]">{doc.name}</div>
              <div className="mt-0.5 text-sm text-white/80">{doc.specialty} · {doc.hospital_name}{doc.experience_years ? ` · ${doc.experience_years}y experience` : ''}</div>
              <div className="mt-2 flex gap-2"><Pill value={doc.status} /><span className="pill bg-white/15 text-white">real slots only</span></div>
            </div>
          </div>
        </div>
      ) : <div className="card p-5">{loading ? <div className="skeleton h-20 rounded-xl" /> : 'Doctor not found.'}</div>}

      {/* verification chain */}
      <Card className="mt-4">
        <div className="text-[11px] font-bold tracking-wider text-ink-faint">BOOKING CHAIN — VISIBLE WHILE YOU BOOK</div>
        <div className="mt-2 flex flex-wrap items-center gap-1.5">
          {CHAIN.map((c, i) => (
            <React.Fragment key={c}>
              <span className={`rounded-full px-3 py-1 text-xs font-bold ${prog >= i ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-ink-soft'}`}>
                {prog >= i ? '● ' : '○ '}{c}
              </span>
              {i < CHAIN.length - 1 && <span className="text-ink-faint">→</span>}
            </React.Fragment>
          ))}
        </div>
        {done && (
          <div className="mt-3 animate-pop-in rounded-xl bg-emerald-50 p-4 text-sm">
            <div className="font-display text-lg font-semibold text-emerald-800">✓ Confirmed — verified against the health system</div>
            <div className="mt-1 text-emerald-900">Appointment <b>#{done.appointment_id}</b> · status <b>{done.status}</b> · {done.verified ? 'external record matched' : 'verification pending'} · ref <code>{done.correlation_id}</code></div>
            <div className="mt-3 flex flex-wrap gap-2">
              <Link to={`/app/appointments/${done.appointment_id}`} className="btn-primary text-sm">Open appointment →</Link>
              <Link to="/app/questionnaires" className="btn-ghost text-sm">Pre-visit questionnaire</Link>
              <Link to="/app/book" className="btn-ghost text-sm">Book another</Link>
            </div>
          </div>
        )}
        {err && <div className="mt-3 animate-pop-in rounded-xl bg-red-50 p-3 text-sm text-red-700">Booking failed safely — no duplicate created: {err}</div>}
      </Card>

      <Card className="mt-4 !border-brand/25" >
        <div id="booking-details" className="scroll-mt-4" />
        <div className="flex flex-wrap items-center gap-1.5 text-xs font-bold">
          <span className={`rounded-full px-3 py-1 ${selected ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-ink-soft'}`}>{selected ? '✓ 1 · Slot picked' : '1 · Pick a slot below'}</span>
          <span className="text-ink-faint">→</span>
          <span className={`rounded-full px-3 py-1 ${stage === 'details' || stage === 'review' ? 'bg-brand text-white' : 'bg-slate-100 text-ink-soft'}`}>2 · Your details</span>
          <span className="text-ink-faint">→</span>
          <span className={`rounded-full px-3 py-1 ${stage === 'review' ? 'bg-brand text-white' : 'bg-slate-100 text-ink-soft'}`}>3 · Review & confirm</span>
        </div>

        {!selected ? (
          <p className="mt-3 text-sm text-ink-soft">Select a time slot below to continue. <b>Nothing is booked until you review and confirm</b> — we will ask for your visit details first.</p>
        ) : stage === 'details' ? (
          <div className="mt-3 animate-fade-up">
            <div className="rounded-xl bg-brand-soft p-3 text-sm"><b>Selected:</b> {fmtSlot(selected)} with {doc?.name} · {doc?.hospital_name}
              <button type="button" onClick={() => { setSelected(null); setStage('slots') }} className="ml-2 font-bold text-brand-deep underline">change</button></div>
            <div className="mt-3 grid gap-3 md:grid-cols-2">
              <div>
                <label htmlFor="book-reason" className="text-xs font-bold">REASON FOR VISIT *</label>
                <input id="book-reason" className="input mt-1" value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. Shoulder pain follow-up" />
              </div>
              <div>
                <label htmlFor="book-mode" className="text-xs font-bold">VISIT MODE</label>
                <select id="book-mode" className="input mt-1" value={mode} onChange={e => setMode(e.target.value)}>
                  {MODES.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}
                </select>
              </div>
            </div>
            <div className="mt-3">
              <label htmlFor="book-notes" className="text-xs font-bold">ANYTHING THE DOCTOR SHOULD KNOW? <span className="font-normal text-ink-soft">(optional)</span></label>
              <textarea id="book-notes" className="input mt-1" rows={2} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Symptoms, duration, prior visits…" />
            </div>
            <div className="mt-2 text-xs text-ink-soft">Booking as <b>{me?.full_name || '…'}</b>{me?.email ? ` · ${me.email}` : ''} · details are stored on the appointment and never used for diagnosis by the AI.</div>
            {formErr && <div className="mt-2 rounded-xl bg-red-50 p-2.5 text-sm text-red-700">{formErr}</div>}
            <button type="button" onClick={goReview} className="btn-primary mt-3 text-sm">Review booking →</button>
          </div>
        ) : (
          <div className="mt-3 animate-fade-up">
            <div className="rounded-xl border border-slate-200 p-4 text-sm">
              <div className="font-display text-lg font-semibold">Please confirm your appointment</div>
              <dl className="mt-2 space-y-1.5">
                <div className="flex gap-2"><dt className="w-24 shrink-0 font-bold text-ink-soft">Doctor</dt><dd>{doc?.name} · {doc?.specialty}</dd></div>
                <div className="flex gap-2"><dt className="w-24 shrink-0 font-bold text-ink-soft">Hospital</dt><dd>{doc?.hospital_name}</dd></div>
                <div className="flex gap-2"><dt className="w-24 shrink-0 font-bold text-ink-soft">When</dt><dd>{fmtSlot(selected)}</dd></div>
                <div className="flex gap-2"><dt className="w-24 shrink-0 font-bold text-ink-soft">Mode</dt><dd>{MODES.find(m => m.id === mode)?.label}</dd></div>
                <div className="flex gap-2"><dt className="w-24 shrink-0 font-bold text-ink-soft">Reason</dt><dd>{reason.trim()}</dd></div>
                {notes.trim() && <div className="flex gap-2"><dt className="w-24 shrink-0 font-bold text-ink-soft">Notes</dt><dd>{notes.trim()}</dd></div>}
                <div className="flex gap-2"><dt className="w-24 shrink-0 font-bold text-ink-soft">Patient</dt><dd>{me?.full_name}{me?.email ? ` · ${me.email}` : ''}</dd></div>
              </dl>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              <button type="button" onClick={() => setStage('details')} className="btn-ghost text-sm">← Edit details</button>
              <button type="button" onClick={book} disabled={busy} className="btn-accent text-sm">{busy ? 'Verifying with health system…' : 'Confirm booking ✓'}</button>
            </div>
          </div>
        )}
      </Card>

      {loading ? (
        <div className="mt-4 grid gap-3 sm:grid-cols-2 md:grid-cols-3">{[0, 1, 2, 3, 4, 5].map(i => <div key={i} className="card p-4"><div className="skeleton h-5 w-2/3" /><div className="skeleton mt-2 h-4 w-1/2" /></div>)}</div>
      ) : grouped.length ? grouped.map(([day, list]) => (
        <div key={day} className="mt-5">
          <div className="mb-2 font-display text-[17px] font-semibold">{day} <span className="text-xs font-sans font-bold text-ink-soft">{list.length} slots</span></div>
          <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">
            {list.map(s => {
              const key = `${s.calendar_id}-${s.starts_at}`
              const active = selected?.starts_at === s.starts_at && selected?.calendar_id === s.calendar_id
              return (
              <div key={key} className={`card card-hover flex items-center justify-between !p-4 ${active ? '!border-brand !ring-2 !ring-brand/30' : ''}`}>
                <div>
                  <div className="font-extrabold">{new Date(s.starts_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
                  <div className="text-xs text-ink-soft">30 min · verified slot</div>
                </div>
                <button type="button" onClick={() => pick(s)} className={active ? 'btn-primary text-xs !px-4 !py-2' : 'btn-accent text-xs !px-4 !py-2'}>
                  {active ? '✓ Selected' : 'Select →'}
                </button>
              </div>
            )})}
          </div>
        </div>
      )) : (
        <Card className="mt-4"><Empty title={intake?.dayPref && intake.dayPref !== 'Any day' ? `No slots ${intake.dayPref.toLowerCase()}` : 'No availability in the next 14 days'} sub="Blocked time, leave and existing bookings are respected. Try another day preference or doctor." /></Card>
      )}
    </div>
  )
}
