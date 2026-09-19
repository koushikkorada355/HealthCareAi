import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client.js'
import { Card, PageHead, Pill, Empty, Trace } from '../../components/ui.jsx'

function Row({ a }) {
  return <Link to={`/app/appointments/${a.id}`} className="flex items-center justify-between py-3 border-t border-slate-100 text-sm hover:text-teal"><span><b>{a.doctor_name}</b> · {new Date(a.starts_at).toLocaleString()} <span className="text-ink-soft">· {a.hospital_name}</span></span><Pill value={a.status} /></Link>
}
export function Upcoming() {
  const [rows, setRows] = useState([])
  useEffect(() => { api('/appointments?upcoming=true').then(setRows).catch(() => {}) }, [])
  return <div><PageHead title="Upcoming appointments" /><Card>{rows.length ? rows.map(a => <Row key={a.id} a={a} />) : <Empty title="No upcoming visits" sub="Book one from the AI assistant." />}</Card></div>
}
export function History() {
  const [rows, setRows] = useState([])
  useEffect(() => { api('/appointments').then(setRows).catch(() => {}) }, [])
  return <div><PageHead title="Appointment history" /><Card>{rows.length ? rows.map(a => <Row key={a.id} a={a} />) : <Empty title="No history yet" />}</Card></div>
}
export function Detail() {
  const { id } = useParams()
  const [a, setA] = useState(null); const [qs, setQs] = useState([]); const [msg, setMsg] = useState('')
  const [showResched, setShowResched] = useState(false); const [working, setWorking] = useState(false)
  const [showCancel, setShowCancel] = useState(false); const [cancelReason, setCancelReason] = useState('')
  const [avail, setAvail] = useState([]); const [availLoading, setAvailLoading] = useState(false); const [selSlot, setSelSlot] = useState(null)
  const load = () => api(`/appointments/${id}`).then(setA).catch(() => {})
  useEffect(() => { load(); api(`/questionnaire-responses?appointment_id=${id}`).then(setQs).catch(() => {}) }, [id])
  if (!a) return <div className="p-8 text-ink-soft">Loading…</div>
  const cancellable = ['pending', 'confirmed', 'rescheduled'].includes(a.status)
  const openResched = async () => {
    const next = !showResched
    setShowResched(next); setShowCancel(false); setSelSlot(null); setMsg('')
    if (next && avail.length === 0) {
      setAvailLoading(true)
      try {
        const r = await api(`/availability?doctor_id=${a.doctor_id}&days_ahead=14`)
        setAvail((r.slots || []).filter(s => s.starts_at !== a.starts_at))
      } catch { setAvail([]) } finally { setAvailLoading(false) }
    }
  }
  const cancel = async () => {
    if (!cancelReason.trim()) { setMsg('Please give a short reason for cancellation — the care team needs it.'); return }
    setMsg(''); setWorking(true)
    try { await api(`/appointments/${id}/cancel`, { method: 'POST', body: { reason: cancelReason.trim() } }); setMsg('Cancelled — slot released, EHR and care team notified.'); setShowCancel(false); setCancelReason(''); load() }
    catch (e) { setMsg(`Could not cancel: ${e.message}`) } finally { setWorking(false) }
  }
  const reschedule = async () => {
    if (!selSlot) { setMsg('Pick a new slot first.'); return }
    setMsg(''); setWorking(true)
    try {
      await api(`/appointments/${id}/reschedule`, { method: 'POST', body: { new_starts_at: selSlot.starts_at, new_ends_at: selSlot.ends_at } })
      setMsg(`Rescheduled to ${new Date(selSlot.starts_at).toLocaleString()} — slot revalidated, EHR updated.`); setShowResched(false); setSelSlot(null); load()
    } catch (ex) { setMsg(`Could not reschedule: ${ex.message}`) } finally { setWorking(false) }
  }
  return <div>
    <PageHead title={`Appointment #${a.id}`} right={<>{cancellable && <><button type="button" onClick={openResched} className="btn-ghost text-sm">Reschedule</button><button type="button" onClick={() => { setShowCancel(true); setShowResched(false) }} className="btn-ghost text-sm !text-crit !border-red-200">Cancel</button></>}{a.status === 'cancelled' && <Link to="/app/book" className="btn-primary text-sm">Book a new visit →</Link>}</>} />
    {msg && <div className="card p-3 mb-3 text-sm animate-pop-in">{msg}</div>}
    {showCancel && cancellable && <div className="card p-5 mb-3 !border-red-200 animate-fade-up" role="dialog" aria-label="Cancel appointment">
      <div className="font-display text-lg font-semibold text-crit">Cancel appointment #{a.id}?</div>
      <ul className="mt-2 list-disc pl-5 text-sm text-ink-soft">
        <li>Your slot on <b>{new Date(a.starts_at).toLocaleString()}</b> will be released for other patients.</li>
        <li>The health system record and the care team will be notified.</li>
        <li>This cannot be undone — you can always book a new slot afterwards.</li>
      </ul>
      <label htmlFor="cancel-reason" className="mt-3 block text-xs font-bold">REASON FOR CANCELLATION *</label>
      <textarea id="cancel-reason" className="input mt-1" rows={2} value={cancelReason} onChange={e => setCancelReason(e.target.value)} placeholder="e.g. Feeling better, schedule conflict…" />
      <div className="mt-3 flex flex-wrap gap-2">
        <button type="button" onClick={cancel} disabled={working} className="btn-primary !bg-crit text-sm">{working ? 'Cancelling…' : 'Confirm cancellation'}</button>
        <button type="button" onClick={() => { setShowCancel(false); setCancelReason('') }} className="btn-ghost text-sm">Keep appointment</button>
      </div>
    </div>}
    {showResched && cancellable && <div className="card p-4 mb-3 animate-fade-up">
      <div className="text-xs font-bold">RESCHEDULE — PICK A REAL SLOT</div>
      <div className="mt-1 text-sm text-ink-soft">Current: <b>{new Date(a.starts_at).toLocaleString()}</b> · the new slot is revalidated against blocks, leave and conflicts before anything moves.</div>
      {availLoading ? <div className="skeleton mt-3 h-16 rounded-xl" /> : avail.length ? (
        <div className="mt-3 grid max-h-64 gap-2 overflow-auto sm:grid-cols-2 md:grid-cols-3">
          {avail.slice(0, 30).map(s => {
            const active = selSlot?.starts_at === s.starts_at
            return <button key={`${s.calendar_id}-${s.starts_at}`} type="button" onClick={() => setSelSlot(s)}
              className={`rounded-xl border p-2.5 text-left text-sm transition ${active ? 'border-brand bg-brand-soft ring-2 ring-brand/30' : 'border-slate-200 bg-white hover:border-brand'}`}>
              <div className="font-bold">{new Date(s.starts_at).toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })}</div>
              <div className="text-ink-soft">{new Date(s.starts_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}{active ? ' ✓' : ''}</div>
            </button>
          })}
        </div>
      ) : <div className="mt-2 text-sm text-ink-soft">No alternative slots in the next 14 days.</div>}
      {selSlot && <div className="mt-3 flex flex-wrap items-center gap-2 rounded-xl bg-brand-soft p-3 text-sm">
        <span>Move to <b>{new Date(selSlot.starts_at).toLocaleString()}</b>?</span>
        <button type="button" onClick={reschedule} disabled={working} className="btn-primary text-sm">{working ? 'Moving…' : 'Confirm move ✓'}</button>
      </div>}
    </div>}
    <div className="grid md:grid-cols-2 gap-4">
      <Card><div className="flex items-center gap-2"><Pill value={a.status} /><Pill value={a.integration_status} /></div>
        <div className="mt-3 text-sm space-y-1"><div><b>When:</b> {new Date(a.starts_at).toLocaleString()} → {new Date(a.ends_at).toLocaleTimeString()}</div><div><b>Doctor:</b> {a.doctor_name}</div><div><b>Reason:</b> {a.reason}</div><div><b>External ID:</b> <code>{a.external_id || '—'}</code></div><div><b>Correlation:</b> <code>{a.correlation_id}</code></div></div></Card>
      <Card><div className="font-bold mb-2">Verification + history</div>
        <div className="text-xs font-bold text-ink-soft">EXTERNAL VERIFICATIONS</div>
        {a.verifications?.length ? a.verifications.map((v, i) => <div key={i} className="text-sm py-1 border-b border-slate-50">{v.method} → <Pill value={v.result} /></div>) : <div className="text-sm text-ink-soft">No verifications yet.</div>}
        <div className="text-xs font-bold text-ink-soft mt-3">STATUS TIMELINE</div>
        {a.history?.map((h, i) => <div key={i} className="text-sm py-1 border-b border-slate-50">{h.from || '∅'} → <b>{h.to}</b> <span className="text-ink-soft">· {h.actor}</span></div>)}
      </Card>
    </div>
    <Card className="mt-4"><div className="font-bold mb-2">Pre-visit questionnaires</div>
      {qs.length ? qs.map(r => <Link key={r.id} to={`/app/questionnaires/${r.id}`} className="flex justify-between text-sm py-2 border-t border-slate-100"><span>{r.questionnaire_title}</span><Pill value={r.status} /></Link>) : <div className="text-sm text-ink-soft">None assigned yet.</div>}</Card>
  </div>
}
export function Questionnaires() {
  const [rows, setRows] = useState([])
  useEffect(() => { api('/questionnaire-responses').then(setRows).catch(() => {}) }, [])
  return <div><PageHead title="Questionnaires" sub="Assigned after booking. Complete conversationally or as a form." />
    <Card>{rows.length ? rows.map(r => <Link key={r.id} to={`/app/questionnaires/${r.id}`} className="flex justify-between text-sm py-2.5 border-t border-slate-100"><span>{r.questionnaire_title} {r.appointment_id ? <span className="text-ink-soft">· appt #{r.appointment_id}</span> : ''}</span><Pill value={r.status} /></Link>) : <Empty title="Nothing due" sub="Book an appointment to get a pre-visit questionnaire." />}</Card></div>
}
export function QFill() {
  const { id } = useParams()
  const [schema, setSchema] = useState([]); const [title, setTitle] = useState(''); const [ans, setAns] = useState({}); const [msg, setMsg] = useState(''); const [step, setStep] = useState(0); const [mode, setMode] = useState('chat'); const [loadErr, setLoadErr] = useState('')
  useEffect(() => { api('/questionnaire-responses').then(rs => { const r = rs.find(x => x.id === Number(id)); if (!r) { setLoadErr('Questionnaire not found — it may have been removed.'); return }; api(`/questionnaires/${r.questionnaire_id}`).then(q => { setSchema(q.schema); setTitle(q.title); setAns(r.answers || {}) }).catch(() => setLoadErr('Could not load this questionnaire — please retry.')) }).catch(() => setLoadErr('Could not load questionnaires — please check your connection and retry.')) }, [id])
  const submit = async () => { try { await api(`/questionnaire-responses/${id}/submit`, { method: 'POST', body: { answers: ans, via: mode === 'chat' ? 'ai_chat' : 'web' } }); setMsg('Submitted — the doctor can now review your responses.') } catch (e) { setMsg(e.message) } }
  const cur = schema[step]
  return <div><PageHead title={title || 'Questionnaire'} right={<button className="btn-ghost text-sm" onClick={() => setMode(mode === 'chat' ? 'form' : 'chat')}>{mode === 'chat' ? 'Switch to form' : 'Switch to chat'}</button>} />
    {loadErr && <div className="card p-3 mb-3 text-sm bg-red-50 text-red-700">{loadErr}</div>}
    {msg && <div className="card p-3 mb-3 text-sm bg-emerald-50">{msg}</div>}
    {mode === 'chat' && cur ? <Card><div className="text-sm text-ink-soft">Question {step + 1} of {schema.length}</div><div className="font-bold text-lg mt-1">{cur.label}</div>
      {cur.type === 'yes_no' ? <div className="flex gap-2 mt-3"><button className="btn-primary" onClick={() => { setAns({ ...ans, [cur.id]: 'yes' }); setStep(Math.min(step + 1, schema.length - 1)) }}>Yes</button><button className="btn-ghost" onClick={() => { setAns({ ...ans, [cur.id]: 'no' }); setStep(Math.min(step + 1, schema.length - 1)) }}>No</button></div>
      : cur.type === 'choice' ? <div className="flex flex-wrap gap-2 mt-3">{(cur.options || []).map(o => <button key={o} className="btn-ghost" onClick={() => { setAns({ ...ans, [cur.id]: o }); setStep(Math.min(step + 1, schema.length - 1)) }}>{o}</button>)}</div>
      : <div className="flex gap-2 mt-3"><input className="input" value={ans[cur.id] || ''} onChange={e => setAns({ ...ans, [cur.id]: e.target.value })} onKeyDown={e => e.key === 'Enter' && setStep(Math.min(step + 1, schema.length - 1))} /><button className="btn-primary" onClick={() => setStep(Math.min(step + 1, schema.length - 1))}>Next</button></div>}
      <div className="flex justify-between mt-5"><button className="btn-ghost text-sm" disabled={step === 0} onClick={() => setStep(step - 1)}>Back</button><button className="btn-primary text-sm" onClick={submit}>Submit all</button></div></Card>
    : <Card>{schema.map(q => <div key={q.id} className="mb-3"><label className="text-sm font-semibold">{q.label}</label><input className="input mt-1" value={ans[q.id] || ''} onChange={e => setAns({ ...ans, [q.id]: e.target.value })} /></div>)}<button className="btn-primary" onClick={submit}>Submit</button></Card>}
  </div>
}
export function Prefs() {
  const [p, setP] = useState({}); const [msg, setMsg] = useState('')
  useEffect(() => { api('/users/me/context').then(r => setP(r.prefs || {})).catch(() => {}) }, [])
  return <div><PageHead title="Preferences" /><Card className="max-w-lg">
    {[['channel', 'Channel (web/sms/voice)'], ['language', 'Language'], ['reminder_hours', 'Reminder lead (hours)']].map(([k, l]) => <div key={k} className="mb-3"><label className="text-xs font-semibold">{l}</label><input className="input mt-1" value={p[k] || ''} onChange={e => setP({ ...p, [k]: e.target.value })} /></div>)}
    <button className="btn-primary" onClick={async () => { await api('/users/me/context', { method: 'PUT', body: { prefs: p } }); setMsg('Saved.') }}>Save</button>{msg && <span className="ml-3 text-sm text-emerald-700">{msg}</span>}</Card></div>
}
export function Profile() {
  const [me, setMe] = useState(null)
  useEffect(() => { api('/auth/me').then(setMe).catch(() => {}) }, [])
  return <div><PageHead title="Profile" /><Card className="max-w-lg">{me ? <div className="text-sm space-y-1"><div><b>Name:</b> {me.full_name}</div><div><b>Email:</b> {me.email}</div><div><b>Role:</b> {me.role}</div></div> : 'Loading…'}</Card></div>
}
