import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client.js'
import { Card, PageHead, Avatar, Cover, Pill, Empty } from '../../components/ui.jsx'
import { hospitalCover } from '../../utils/photos.js'

/* Patient hospital detail: everything about one hospital on a single page.
 * Read-only discovery (CRUD booking happens from the slot picker).
 */
export default function HospitalDetail() {
  const { id } = useParams()
  const [h, setH] = useState(null); const [rev, setRev] = useState(null); const [msg, setMsg] = useState('')
  useEffect(() => {
    api(`/hospitals/${id}`).then(setH).catch(() => setMsg('Could not load this hospital.'))
    api(`/reviews/summary?hospital_id=${id}`).then(setRev).catch(() => {})
  }, [id])
  if (!h) return <div className="p-8">{msg ? <Card><Empty title="Not available" sub={msg} /><Link to="/app/hospitals" className="btn-ghost text-sm mt-3 inline-block">← All hospitals</Link></Card> : 'Loading…'}</div>
  const docs = h.doctors || []
  return <div>
    <Cover src={h.cover_url || hospitalCover(h.slug)} height={190}>
      <div className="flex items-end justify-between gap-2">
        <div><div className="font-display text-2xl font-semibold text-white drop-shadow">{h.name}</div>
        <div className="text-sm text-white/85">{h.city} · {h.address}</div></div>
        <Pill value={h.status} />
      </div>
    </Cover>
    <div className="grid md:grid-cols-3 gap-4">
      <Card className="md:col-span-2"><div className="font-bold mb-2">About</div>
        <div className="flex flex-wrap gap-2 text-sm">
          <span className="pill bg-amber-50 text-amber-700">★ {h.avg_rating ?? 0} ({h.review_count ?? 0} reviews)</span>
          <span className="pill bg-brand-soft text-brand-ink">{h.doctor_count ?? docs.length} doctors</span>
          <span className="pill bg-slate-100 text-slate-600">{h.completed_visits ?? 0} completed visits</span>
        </div>
        <div className="mt-3 grid sm:grid-cols-2 gap-3 text-sm">
          <div><div className="text-xs font-bold text-ink-soft">CONTACT</div><div>{h.phone || '—'} · {h.contact_email || ''}</div></div>
          <div><div className="text-xs font-bold text-ink-soft">HOURS</div><HoursMini value={h.operating_hours} /></div>
        </div>
        <div className="mt-3"><div className="text-xs font-bold text-ink-soft">SERVICES</div><ServiceChips value={h.services} /></div>
        <div className="mt-3 grid sm:grid-cols-2 gap-3">
          <div><div className="text-xs font-bold text-ink-soft">DEPARTMENTS</div><div className="mt-1 flex flex-wrap gap-1.5">{(h.departments || []).map(d => <span key={d.id} className="pill bg-slate-100 text-slate-600 text-xs">{d.name}</span>) || <span className="text-sm text-ink-soft">—</span>}</div></div>
          <div><div className="text-xs font-bold text-ink-soft">SPECIALTIES</div><div className="mt-1 flex flex-wrap gap-1.5">{(h.specialties || []).slice(0, 10).map(s => <span key={s.id} className="pill bg-violet-50 text-violet-700 text-xs">{s.name}</span>)}</div></div>
        </div>
        <div className="mt-4 flex flex-wrap gap-2">
          <Link to={`/app/doctors?hospital_id=${h.id}`} className="btn-primary text-sm">View doctors →</Link>
          <Link to="/app/book" className="btn-ghost text-sm">Quick book</Link>
        </div>
      </Card>
      <div className="space-y-4">
        <Card><div className="font-bold mb-2">Patient rating</div>
          {rev && rev.count ? <div><div className="text-3xl font-bold">★ {rev.avg}</div><div className="text-sm text-ink-soft">{rev.count} reviews</div><div className="mt-2 text-sm space-y-1">{[5, 4, 3, 2, 1].map(s => <div key={s} className="flex justify-between"><span>★ {s}</span><b>{rev.dist?.[s] || 0}</b></div>)}</div></div>
          : <div className="text-sm text-ink-soft">No patient reviews yet.</div>}
        </Card>
        <Card><div className="font-bold mb-2">Systems</div><div className="text-sm text-ink-soft">EHR: {h.ehr_vendor} · Facility <code className="text-xs">{h.external_facility_id}</code></div></Card>
      </div>
    </div>
    <div className="mt-6"><div className="mb-2 font-display text-xl font-semibold">Doctors at {h.name} <span className="text-sm font-sans text-ink-soft">({docs.length})</span></div>
      {docs.length ? <div className="grid md:grid-cols-2 gap-4">{docs.map(d => (
        <Card key={d.id} className="card-hover flex gap-4"><Avatar name={d.name} size={60} photo={d.photo_url} seed={d.id} plain={false} />
          <div className="flex-1"><div className="font-bold">{d.name}</div><div className="text-sm text-ink-soft">{d.specialty} · {d.experience_years}y exp · ★ {d.rating}</div>
          <Link to={`/app/book/${d.id}`} className="btn-primary text-sm mt-2 inline-block">View slots →</Link></div></Card>))}</div>
      : <Card><Empty title="No active doctors listed" sub="Check back soon or browse other hospitals." /></Card>}
    </div>
  </div>
}

function HoursMini({ value }) {
  let h = {}
  try { h = JSON.parse(value || '{}') } catch { h = {} }
  const days = [['mon', 'M'], ['tue', 'T'], ['wed', 'W'], ['thu', 'T'], ['fri', 'F'], ['sat', 'S'], ['sun', 'S']]
  return <div className="flex gap-1">{days.map(([k, l]) => <span key={k} title={k} className={`rounded-lg px-1.5 py-0.5 text-xs font-bold ${h[k]?.length ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-400'}`}>{l}</span>)}</div>
}

function ServiceChips({ value }) {
  let s = []
  try { s = JSON.parse(value || '[]') } catch { s = [] }
  if (typeof s === 'string') s = [s]
  return <div className="mt-1 flex flex-wrap gap-1.5">{s.length ? s.map(x => <span key={x} className="pill bg-brand-soft text-brand-ink text-xs">{x}</span>) : <span className="text-sm text-ink-soft">—</span>}</div>
}
