import React, { useEffect, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../../api/client.js'
import { Card, PageHead, Avatar, Cover, Pill } from '../../components/ui.jsx'
import { hospitalCover } from '../../utils/photos.js'

export function Hospitals() {
  const [rows, setRows] = useState([]); const [q, setQ] = useState(''); const [city, setCity] = useState('')
  const load = (qq = q, cc = city) => {
    const p = new URLSearchParams()
    if (qq) p.set('q', qq)
    if (cc) p.set('city', cc)
    api(`/hospitals${p.toString() ? `?${p}` : ''}`).then(setRows).catch(() => {})
  }
  useEffect(() => { load('', '') }, [])
  const list = rows.filter(h => !q || h.name.toLowerCase().includes(q.toLowerCase()))
  return <div><PageHead title="Hospitals" sub="Approved hospitals only. Filter by city for 'near me'." />
    <div className="flex flex-wrap gap-2 mb-4">
      <input className="input max-w-xs" placeholder="Search hospitals…" value={q} onChange={e => setQ(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()} />
      <input className="input max-w-xs" placeholder="City, e.g. Springfield…" value={city} onChange={e => setCity(e.target.value)} onKeyDown={e => e.key === 'Enter' && load()} />
      <button type="button" className="btn-primary" onClick={() => load()}>Search</button>
    </div>
    <div className="grid md:grid-cols-2 gap-4">{list.map(h => (
      <Card key={h.id} className="card-hover !p-0 overflow-hidden">
        <Cover src={h.cover_url || hospitalCover(h.slug)} height={140}>
          <div className="flex items-end justify-between gap-2">
            <span className="font-display text-lg font-semibold text-white drop-shadow">{h.name}</span>
            <Pill value={h.status} />
          </div>
        </Cover>
        <div className="p-5 pt-3">
          <div className="text-sm text-ink-soft">{h.city} · EHR: {h.ehr_vendor}</div>
          <div className="mt-3 flex gap-2">
            <Link to={`/app/doctors?hospital_id=${h.id}`} className="btn-primary text-sm">View doctors →</Link>
            <Link to="/app/book" className="btn-ghost text-sm">Quick book</Link>
          </div>
        </div>
      </Card>))}</div></div>
}
export function Doctors() {
  const [rows, setRows] = useState([]); const [q, setQ] = useState(''); const [spec, setSpec] = useState('')
  const [sp] = useSearchParams()
  const hid = sp.get('hospital_id') || ''
  const query = () => api(`/doctors?${hid ? `hospital_id=${hid}&` : ''}${spec ? `specialty=${spec}&` : ''}${q ? `q=${q}` : ''}`).then(setRows).catch(() => {})
  useEffect(() => { query() }, [hid, spec])
  return <div><PageHead title="Find doctors" sub="Only active doctors with real calendars." />
    <div className="flex flex-wrap gap-2 mb-4">
      <input className="input max-w-xs" placeholder="Name…" value={q} onChange={e => setQ(e.target.value)} />
      <select className="input max-w-xs" value={spec} onChange={e => setSpec(e.target.value)}><option value="">All specialties</option>{['Orthopedics','Cardiology','Dermatology','Neurology','Pediatrics','General Medicine'].map(s => <option key={s}>{s}</option>)}</select>
      <button type="button" className="btn-primary" onClick={query}>Search</button>
    </div>
    <div className="grid md:grid-cols-2 gap-4">{rows.map(d => (
      <Card key={d.id} className="card-hover flex gap-4"><Avatar name={d.name} size={64} photo={d.photo_url} seed={d.id} plain={false} />
        <div className="flex-1"><div className="font-bold">{d.name}</div><div className="text-sm text-ink-soft">{d.specialty} · {d.hospital_name} · {d.experience_years}y exp · ★ {d.rating}</div>
        <div className="mt-1"><Pill value={d.status} /></div>
        <Link to={`/app/doctors/${d.id}/slots`} className="btn-primary text-sm mt-2 inline-block">Check availability</Link></div></Card>))}</div></div>
}
export function Slots() {
  const { id } = useParams()
  const [slots, setSlots] = useState([]); const [doc, setDoc] = useState(null); const [busy, setBusy] = useState(null); const [msg, setMsg] = useState('')
  const [selected, setSelected] = useState(null); const [reason, setReason] = useState(''); const [mode, setMode] = useState('in_person')
  const load = () => { api(`/doctors/${id}`).then(setDoc).catch(() => {}); api(`/availability?doctor_id=${id}&days_ahead=7`).then(r => setSlots(r.slots || [])).catch(() => {}) }
  useEffect(load, [id])
  const book = async () => {
    if (!selected || !reason.trim()) { setMsg('Pick a slot and tell us the reason for your visit first.'); return }
    const s = selected
    setBusy(`${s.calendar_id}-${s.starts_at}`); setMsg('')
    try {
      const me = await api('/auth/me')
      if (!doc) throw new Error('Doctor details are still loading — please retry.')
      const r = await api('/appointments', { method: 'POST', body: { hospital_id: doc.hospital_id, doctor_id: doc.id, patient_id: me.patient_id, starts_at: s.starts_at, ends_at: s.ends_at, calendar_id: s.calendar_id, mode, reason: reason.trim(), idempotency_key: `web-${me.id}-${doc.id}-${s.starts_at}-${Date.now().toString(36)}` } })
      setMsg(`Confirmed! #${r.appointment_id} verified (${r.correlation_id}).`)
      setSelected(null); setReason('')
      load()
    } catch (e) { setMsg(`Could not book: ${e.message}`) } finally { setBusy(null) }
  }
  return <div><PageHead title={doc ? doc.name : 'Availability'} sub="Real slots from the scheduling engine — never invented. Select a slot, add details, then confirm." />
    {msg && <div className="card p-3 mb-3 text-sm bg-emerald-50">{msg}</div>}
    {selected && <div className="card p-4 mb-3 !border-brand/25 animate-fade-up">
      <div className="text-sm"><b>Selected:</b> {new Date(selected.starts_at).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
        <button type="button" onClick={() => setSelected(null)} className="ml-2 font-bold text-brand-deep underline">change</button></div>
      <div className="mt-2 grid gap-2 md:grid-cols-[1fr_180px_auto]">
        <label htmlFor="slot-reason" className="sr-only">Reason for visit</label>
        <input id="slot-reason" className="input" placeholder="Reason for visit (required)…" value={reason} onChange={e => setReason(e.target.value)} />
        <select className="input" aria-label="Visit mode" value={mode} onChange={e => setMode(e.target.value)}><option value="in_person">In person</option><option value="video">Video call</option><option value="phone">Phone call</option></select>
        <button type="button" disabled={!!busy || !reason.trim()} onClick={book} className="btn-accent text-xs">{busy ? 'Verifying…' : 'Confirm ✓'}</button>
      </div>
    </div>}
    <div className="grid sm:grid-cols-2 md:grid-cols-3 gap-3">{slots.map(s => {
      const key = `${s.calendar_id}-${s.starts_at}`
      const active = selected?.starts_at === s.starts_at && selected?.calendar_id === s.calendar_id
      return (
      <Card key={key} className={`flex items-center justify-between ${active ? '!border-brand !ring-2 !ring-brand/30' : ''}`}><div><div className="font-bold text-sm">{new Date(s.starts_at).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric' })}</div><div className="text-sm text-ink-soft">{new Date(s.starts_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div></div>
        <button type="button" onClick={() => { setSelected(s); setMsg('') }} className={active ? 'btn-primary text-xs' : 'btn-ghost text-xs'}>{active ? '✓ Selected' : 'Select'}</button></Card>)})}
    </div>{!slots.length && <div className="text-sm text-ink-soft mt-4">No availability in the next 7 days (blocked / leave / booked respected).</div>}</div>
}
