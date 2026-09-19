import React, { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { api } from '../../api/client.js'
import { Card, Pill, Avatar, Empty } from '../../components/ui.jsx'
import { hospitalCover } from '../../utils/photos.js'
import SlotPicker from './SlotPicker.jsx'

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
      {/* intake — light template: white cards over a soft banner */}
      <div className="relative overflow-hidden rounded-2xl border border-brand/15 bg-gradient-to-br from-brand-soft via-white to-apricot-soft p-6 shadow-lift md:p-8">
        <div className="relative">
          <div className="inline-block rounded-full bg-brand px-3 py-1 text-[11px] font-bold tracking-wider text-white">✦ STEP 1 OF 2 · TELL US ABOUT YOUR VISIT</div>
          <h1 className="font-display mt-2 text-3xl font-semibold text-ink md:text-4xl">What brings you in today?</h1>
          <p className="mt-1 max-w-xl text-sm text-ink-soft">Answer a few quick questions and we will match you with the right doctors and their real availability. Nothing is booked on this page.</p>

          <Card className="mt-4 max-w-2xl !p-5">
          <label htmlFor="book-problem" className="block text-xs font-bold tracking-wide">1 · WHAT IS THE PROBLEM? *</label>
          <textarea id="book-problem" className="input mt-1" rows={2}
            placeholder='Describe it in your own words — e.g. "shoulder pain since last week"' value={problem} onChange={e => onProblem(e.target.value)} />
          <div className="mt-2 flex flex-wrap gap-2">
            {PROBLEM_CHIPS.map(c => (
              <button key={c} type="button" onClick={() => onProblem(problem.trim() ? `${problem.trim()} + ${c.toLowerCase()}` : c)}
                className="rounded-full bg-slate-100 px-3 py-1.5 text-xs font-bold text-ink transition hover:bg-brand-soft hover:text-brand-ink">+ {c}</button>
            ))}
          </div>
          {detectSpec(problem) && <div className="mt-2 text-xs font-bold text-ink-soft">Looks like <span className="rounded-full bg-brand px-2 py-0.5 text-white">{detectSpec(problem)}</span> — you can change it below.</div>}

          <div className="mt-4 text-xs font-bold tracking-wide">2 · WHICH SPECIALTY?</div>
          <div className="mt-2 flex flex-wrap gap-2">
            {SPECIALTIES.map(s => (
              <button key={s} type="button" onClick={() => pickSpec(s)}
                className={`rounded-full px-4 py-1.5 text-xs font-bold transition ${spec === s ? 'bg-brand text-white shadow-lift' : 'bg-slate-100 text-ink-soft hover:bg-brand-soft hover:text-brand-ink'}`}>{s}{spec === s ? ' ✓' : ''}</button>
            ))}
          </div>

          <div className="mt-4 grid gap-3 sm:grid-cols-2">
            <div>
              <label htmlFor="book-hosp" className="block text-xs font-bold tracking-wide">3 · PREFERRED HOSPITAL</label>
              <select id="book-hosp" className="input mt-1" value={hospId} onChange={e => setHospId(e.target.value)}>
                <option value="">No preference</option>
                {hospitals.map(h => <option key={h.id} value={h.id}>{h.name}</option>)}
              </select>
            </div>
            <div>
              <div className="text-xs font-bold tracking-wide">4 · PREFERRED DAY</div>
              <div className="mt-1 flex flex-wrap gap-1.5">
                {DAY_OPTS.map(dy => (
                  <button key={dy} type="button" onClick={() => setDayPref(dy)}
                    className={`rounded-full px-3 py-2 text-xs font-bold transition ${dayPref === dy ? 'bg-brand text-white shadow-lift' : 'bg-slate-100 text-ink-soft hover:bg-brand-soft'}`}>{dy}</button>
                ))}
              </div>
            </div>
          </div>

          {intakeErr && <div className="mt-3 max-w-xl rounded-xl bg-red-50 p-2.5 text-sm font-semibold text-red-700">{intakeErr}</div>}
          <button type="button" onClick={findDoctors} className="btn-primary mt-4 !px-6 !py-3">
            Find matching doctors →
          </button>
          </Card>
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
      {/* hospital strip — rating-first compact cards */}
      <div className="mt-2 text-xs font-bold tracking-wide text-ink-soft">HOSPITALS</div>
      <div className="stagger mt-2 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <button key="" type="button" onClick={() => setHospId('')}
          className={`rounded-2xl border p-3 text-left shadow-card transition hover:-translate-y-0.5 ${!hospId ? 'border-brand ring-2 ring-brand/30 bg-brand-soft/40' : 'border-slate-100 bg-white'}`}>
          <div className="font-bold text-sm">All hospitals</div><div className="text-xs text-ink-soft">Everywhere · {doctors.length} doctors</div>
        </button>
        {hospitals.map(h => {
          const sel = String(h.id) === hospId
          const n = doctors.filter(d => String(d.hospital_id) === String(h.id)).length
          return (
          <button key={h.id} type="button" onClick={() => setHospId(sel ? '' : String(h.id))}
            className={`rounded-2xl border p-3 text-left shadow-card transition hover:-translate-y-0.5 ${sel ? 'border-brand ring-2 ring-brand/30 bg-brand-soft/40' : 'border-slate-100 bg-white'}`}>
            <div className="flex items-center justify-between gap-2"><span className="font-bold text-sm truncate">{h.name}</span>{sel && <span className="text-brand-deep font-bold">✓</span>}</div>
            <div className="text-xs text-ink-soft">{h.city}</div>
            <div className="mt-1 text-xs"><b>★ {h.avg_rating ?? 0}</b> <span className="text-ink-soft">({h.review_count ?? 0}) · {n} doctors</span></div>
          </button>
        )})}
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
            <Card key={d.id} className="card-hover !p-5">
              <div className="flex gap-4">
                <Avatar name={d.name} size={72} photo={d.photo_url} seed={d.id} plain={false} />
                <div className="min-w-0 flex-1">
                  <div className="font-display text-lg font-semibold leading-tight">{d.name}</div>
                  <div className="mt-0.5 text-sm"><b>★ {d.avg_rating ?? d.rating ?? 0}</b> <span className="text-ink-soft">({d.review_count ?? 0} reviews) · {d.specialty}</span></div>
                  <div className="mt-0.5 text-sm text-ink-soft">{d.hospital_name}{d.hospital_city ? ` · ${d.hospital_city}` : ''}{d.experience_years ? ` · ${d.experience_years}y exp` : ''} · <Pill value={d.status} /></div>
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

/* ================= PAGE 2 — Pick slot (doctor header + unified picker) ================= */

export function BookSlots() {
  const { id } = useParams()
  const nav = useNavigate()
  const [doc, setDoc] = useState(null)
  const [loading, setLoading] = useState(true)
  // answers carried over from the Page-1 intake questionnaire
  const [intake, setIntake] = useState(null)

  useEffect(() => {
    setLoading(true)
    try {
      const saved = JSON.parse(sessionStorage.getItem('book_intake') || 'null')
      if (saved?.problem) setIntake(saved)
    } catch { /* intake stays empty */ }
    api(`/doctors/${id}`).catch(() => null).then(setDoc).finally(() => setLoading(false))
  }, [id])

  const goConfirm = (slot, mode) => {
    const q = new URLSearchParams({ starts_at: slot.starts_at, ends_at: slot.ends_at, calendar_id: slot.calendar_id, mode })
    nav(`/app/book/${id}/confirm?${q}`, { state: { slot, mode } })
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
        </div>
      )}
      {doc ? (
        <div className="hero-gradient relative overflow-hidden rounded-2xl p-5 shadow-lift md:p-6">
          <div className="flex items-center gap-4">
            <Avatar name={doc.name} size={68} photo={doc.photo_url} seed={doc.id} plain={false} />
            <div className="text-white">
              <div className="font-display text-2xl font-semibold leading-tight md:text-[28px]">{doc.name}</div>
              <div className="mt-0.5 text-sm text-white/80">{doc.specialty} · {doc.hospital_name}{doc.experience_years ? ` · ${doc.experience_years}y experience` : ''} · ★ {doc.avg_rating ?? doc.rating ?? 0} ({doc.review_count ?? 0} reviews)</div>
              <div className="mt-2 flex gap-2"><Pill value={doc.status} /><span className="pill bg-white/15 text-white">real slots only</span></div>
            </div>
          </div>
        </div>
      ) : <div className="card p-5">{loading ? <div className="skeleton h-20 rounded-xl" /> : 'Doctor not found.'}</div>}

      <div className="mt-5"><div className="mb-3 font-display text-xl font-semibold">Pick a time <span className="text-sm font-sans text-ink-soft">— click a slot to continue to details</span></div>
        {loading ? <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">{[0, 1, 2, 3, 4, 5].map(i => <div key={i} className="card p-4"><div className="skeleton h-5 w-2/3" /><div className="skeleton mt-2 h-4 w-1/2" /></div>)}</div>
        : <SlotPicker doctorId={id} dayPref={intake?.dayPref || 'Any day'} onPick={goConfirm} />}
      </div>
    </div>
  )
}
