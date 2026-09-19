import React, { useEffect, useState } from 'react'
import { Link, useLocation, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../../api/client.js'
import { Card, Pill, Avatar, Empty } from '../../components/ui.jsx'

const MODES = [
  { id: 'in_person', label: 'In person' },
  { id: 'video', label: 'Video call' },
  { id: 'phone', label: 'Phone call' },
]

const CHAIN = ['Requested', 'EHR write', 'External verification', 'State sync', 'Confirmed + notified']

function fmtSlot(s) {
  if (!s?.starts_at) return '—'
  const d = new Date(s.starts_at)
  return `${d.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' })} · ${d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}`
}

/* Dedicated confirm page: slot arrives via navigation state, with URL
 * fallback (?starts_at=&ends_at=&calendar_id=&mode=) so refresh never loses it.
 */
export default function BookConfirm() {
  const { id } = useParams()
  const loc = useLocation(); const nav = useNavigate(); const [sp] = useSearchParams()
  const [doc, setDoc] = useState(null); const [me, setMe] = useState(null)
  const [slot, setSlot] = useState(loc.state?.slot || null)
  const [reason, setReason] = useState(''); const [mode, setMode] = useState(loc.state?.mode || sp.get('mode') || 'in_person'); const [notes, setNotes] = useState('')
  const [formErr, setFormErr] = useState(''); const [busy, setBusy] = useState(false); const [done, setDone] = useState(null); const [err, setErr] = useState(''); const [prog, setProg] = useState(-1)

  useEffect(() => {
    try {
      const saved = JSON.parse(sessionStorage.getItem('book_intake') || 'null')
      if (saved?.problem) setReason(saved.problem)
    } catch { /* reason stays empty */ }
    Promise.all([api(`/doctors/${id}`).catch(() => null), api('/auth/me').catch(() => null)]).then(([d, u]) => { setDoc(d); setMe(u) })
  }, [id])

  useEffect(() => {
    if (slot || !sp.get('starts_at')) return
    setSlot({ starts_at: sp.get('starts_at'), ends_at: sp.get('ends_at'), calendar_id: Number(sp.get('calendar_id')) })
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  const book = async () => {
    setFormErr('')
    if (!slot) { setFormErr('No slot selected — go back and pick one.'); return }
    if (!reason.trim()) { setFormErr('Please tell us the reason for your visit — it helps the doctor prepare.'); return }
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
          starts_at: slot.starts_at, ends_at: slot.ends_at, calendar_id: slot.calendar_id,
          mode, reason: fullReason,
          idempotency_key: `book2page-${u.id}-${doc.id}-${slot.starts_at}-${Date.now().toString(36)}`,
        },
      })
      setProg(CHAIN.length - 1); setDone(r)
    } catch (e) { setErr(e.message); setProg(-1) }
    finally { clearInterval(tick); setBusy(false) }
  }

  return <div>
    <Link to={`/app/book/${id}`} className="mb-3 inline-block text-sm font-bold text-brand-deep hover:underline">← Change slot</Link>
    <div className="hero-gradient relative overflow-hidden rounded-2xl p-5 shadow-lift md:p-6">
      <div className="flex items-center gap-4">
        {doc && <Avatar name={doc.name} size={64} photo={doc.photo_url} seed={doc.id} plain={false} />}
        <div className="text-white">
          <div className="text-xs font-bold tracking-widest opacity-80">CONFIRM YOUR VISIT</div>
          <div className="font-display text-2xl font-semibold leading-tight">{doc ? doc.name : 'Loading…'}</div>
          <div className="mt-0.5 text-sm text-white/80">{slot ? fmtSlot(slot) : 'Pick a slot first'} · {MODES.find(m => m.id === mode)?.label}</div>
        </div>
      </div>
    </div>
    {!slot ? (
      <Card className="mt-4"><Empty title="No slot selected" sub="Go back and pick a time first — nothing is booked." /><Link to={`/app/book/${id}`} className="btn-primary text-sm mt-3 inline-block">Pick a slot →</Link></Card>
    ) : done ? (
      <Card className="mt-4"><div className="font-display text-lg font-semibold text-emerald-800">✓ Confirmed — verified against the health system</div>
        <div className="mt-1 text-sm">Appointment <b>#{done.appointment_id}</b> · status <b>{done.status}</b> · {done.verified ? 'external record matched' : 'verification pending'} · ref <code>{done.correlation_id}</code></div>
        <div className="mt-3 flex flex-wrap gap-2">
          <Link to={`/app/appointments/${done.appointment_id}`} className="btn-primary text-sm">Open appointment →</Link>
          <Link to="/app/questionnaires" className="btn-ghost text-sm">Pre-visit questionnaire</Link>
          <Link to="/app/book" className="btn-ghost text-sm">Book another</Link>
        </div></Card>
    ) : (
      <Card className="mt-4">
        <div className="grid gap-3 md:grid-cols-2">
          <div>
            <div className="font-bold mb-2">Your slot</div>
            <div className="rounded-xl bg-brand-soft p-3 text-sm"><b>{fmtSlot(slot)}</b><div className="text-ink-soft">with {doc?.name} · {doc?.hospital_name}</div></div>
            <div className="mt-3"><label htmlFor="cf-mode" className="text-xs font-bold">VISIT MODE</label>
              <select id="cf-mode" className="input mt-1" value={mode} onChange={e => setMode(e.target.value)}>{MODES.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}</select></div>
          </div>
          <div>
            <div className="font-bold mb-2">Visit details</div>
            <label htmlFor="cf-reason" className="text-xs font-bold">REASON FOR VISIT *</label>
            <input id="cf-reason" className="input mt-1" value={reason} onChange={e => setReason(e.target.value)} placeholder="e.g. Shoulder pain follow-up" />
            <label htmlFor="cf-notes" className="mt-3 block text-xs font-bold">ANYTHING THE DOCTOR SHOULD KNOW? <span className="font-normal text-ink-soft">(optional)</span></label>
            <textarea id="cf-notes" className="input mt-1" rows={3} value={notes} onChange={e => setNotes(e.target.value)} placeholder="Symptoms, duration, prior visits…" />
            <div className="mt-2 text-xs text-ink-soft">Booking as <b>{me?.full_name || '…'}</b> · details are stored on the appointment and never used for diagnosis by the AI.</div>
          </div>
        </div>
        <div className="mt-3">
          <div className="text-[11px] font-bold tracking-wider text-ink-faint">WHILE YOU CONFIRM — REQUESTED → EHR → VERIFIED → SYNCED → CONFIRMED</div>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">{CHAIN.map((c, i) => <span key={c} className={`rounded-full px-3 py-1 text-xs font-bold ${prog >= i ? 'bg-emerald-500 text-white' : 'bg-slate-100 text-ink-soft'}`}>{prog >= i ? '● ' : '○ '}{c}</span>)}</div>
        </div>
        {formErr && <div className="mt-3 rounded-xl bg-red-50 p-2.5 text-sm text-red-700">{formErr}</div>}
        {err && <div className="mt-3 rounded-xl bg-red-50 p-3 text-sm text-red-700">Booking failed safely — no duplicate created: {err}</div>}
        <button type="button" onClick={book} disabled={busy} className="btn-accent mt-3 text-sm">{busy ? 'Verifying with health system…' : 'Confirm booking ✓'}</button>
      </Card>
    )}
  </div>
}
