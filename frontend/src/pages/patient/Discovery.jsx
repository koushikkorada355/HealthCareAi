import React, { useEffect, useState } from 'react'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'
import { api } from '../../api/client.js'
import { Card, PageHead, Avatar, Cover, Pill } from '../../components/ui.jsx'
import { hospitalCover } from '../../utils/photos.js'
import SlotPicker from './SlotPicker.jsx'

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
        <Link to={`/app/hospitals/${h.id}`}><Cover src={h.cover_url || hospitalCover(h.slug)} height={140}>
          <div className="flex items-end justify-between gap-2">
            <span className="font-display text-lg font-semibold text-white drop-shadow">{h.name}</span>
            <Pill value={h.status} />
          </div>
        </Cover></Link>
        <div className="p-5 pt-3">
          <div className="text-sm text-ink-soft">{h.city} · {h.address} · {h.doctor_count ?? 0} doctors · ★ {h.avg_rating ?? 0} ({h.review_count ?? 0} reviews)</div>
          <div className="mt-3 flex gap-2">
            <Link to={`/app/hospitals/${h.id}`} className="btn-primary text-sm">Open hospital →</Link>
            <Link to={`/app/doctors?hospital_id=${h.id}`} className="btn-ghost text-sm">View doctors</Link>
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
        <div className="flex-1"><div className="font-bold">{d.name}</div><div className="text-sm text-ink-soft">{d.specialty} · {d.hospital_name}{d.hospital_city ? ` (${d.hospital_city})` : ''} · {d.experience_years}y exp · ★ {d.rating}{d.review_count != null ? ` (${d.review_count} reviews)` : ''}</div>
        <div className="mt-1"><Pill value={d.status} /></div>
        <Link to={`/app/doctors/${d.id}/slots`} className="btn-primary text-sm mt-2 inline-block">Check availability</Link></div></Card>))}</div></div>
}
export function Slots() {
  const { id } = useParams()
  const nav = useNavigate()
  const [doc, setDoc] = useState(null); const [loading, setLoading] = useState(true)
  useEffect(() => { api(`/doctors/${id}`).then(setDoc).catch(() => {}).finally(() => setLoading(false)) }, [id])
  const goConfirm = (slot, mode) => {
    const q = new URLSearchParams({ starts_at: slot.starts_at, ends_at: slot.ends_at, calendar_id: slot.calendar_id, mode })
    nav(`/app/book/${id}/confirm?${q}`, { state: { slot, mode } })
  }
  return <div><PageHead title={doc ? doc.name : 'Availability'} sub="Real slots from the scheduling engine — never invented. Pick a slot to continue to details." />
    {loading ? <div className="card p-5"><div className="skeleton h-16 rounded-xl" /></div>
    : !doc ? <div className="card p-5">Doctor not found.</div>
    : <><Card className="mb-4 flex gap-4"><Avatar name={doc.name} size={64} photo={doc.photo_url} seed={doc.id} plain={false} /><div className="text-sm"><div className="font-bold text-base">{doc.name} · ★ {doc.avg_rating ?? doc.rating} ({doc.review_count ?? 0} reviews)</div><div className="text-ink-soft">{doc.specialty} · {doc.hospital_name}{doc.hospital_city ? ` (${doc.hospital_city})` : ''} · {doc.experience_years}y exp · {doc.qualifications}</div><div className="text-ink-soft">Languages: {doc.languages} · {doc.completed_visits ?? 0} completed visits</div></div></Card>
    <SlotPicker doctorId={id} onPick={goConfirm} compact /></>}
  </div>
}
