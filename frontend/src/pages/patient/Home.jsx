import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client.js'
import { Card, PageHead, Pill, Avatar, Empty } from '../../components/ui.jsx'

function DoctorCard({ d }) {
  return <Card className="card-hover flex gap-4">
    <Avatar name={d.name} size={64} photo={d.photo_url} seed={d.id} plain={false} />
    <div className="flex-1 min-w-0">
      <div className="font-bold leading-tight">{d.name}</div>
      <div className="text-sm text-ink-soft">{d.specialty} · {d.hospital_name}{d.hospital_city ? ` (${d.hospital_city})` : ''}</div>
      <div className="mt-1 flex flex-wrap items-center gap-2 text-sm"><span className="font-bold">★ {d.avg_rating ?? d.rating ?? 0}</span><span className="text-ink-soft">({d.review_count ?? 0} reviews)</span>{d.experience_years ? <span className="text-ink-soft">· {d.experience_years}y exp</span> : null}<Pill value={d.status} /></div>
      <div className="mt-2 flex gap-2">
        <Link to={`/app/book/${d.id}`} className="btn-primary text-sm">View slots →</Link>
        <Link to={`/app/doctors/${d.id}/slots`} className="btn-ghost text-sm">Classic view</Link>
      </div>
    </div>
  </Card>
}

export function DoctorSpotlight() {
  const [docs, setDocs] = useState([]); const [recentIds, setRecentIds] = useState([]); const [f, setF] = useState('top')
  useEffect(() => {
    api('/doctors').then(setDocs).catch(() => {})
    api('/appointments').then(as => {
      const seen = []; const ids = new Set()
      as.forEach(a => { if (!ids.has(a.doctor_id)) { ids.add(a.doctor_id); seen.push(a.doctor_id) } })
      setRecentIds(seen.slice(0, 4))
    }).catch(() => {})
  }, [])
  const top = [...docs].sort((a, b) => (b.avg_rating ?? b.rating ?? 0) - (a.avg_rating ?? a.rating ?? 0)).slice(0, 4)
  const recent = recentIds.map(id => docs.find(d => d.id === id)).filter(Boolean)
  const list = f === 'top' ? top : f === 'recent' ? recent : docs.slice(0, 4)
  return <div>
    <div className="flex flex-wrap items-center gap-2 mb-3">{[['top', 'Top rated'], ['recent', 'Recently visited'], ['all', 'Browse']].map(([v, l]) => <button key={v} type="button" onClick={() => setF(v)} className={f === v ? 'btn-primary text-sm' : 'btn-ghost text-sm'}>{l}</button>)}
      <Link to="/app/doctors" className="ml-auto text-sm font-bold text-brand-deep hover:underline">All doctors →</Link></div>
    {list.length ? <div className="grid md:grid-cols-2 gap-4">{list.map(d => <DoctorCard key={d.id} d={d} />)}</div>
    : <Card><Empty title={f === 'recent' ? 'No visits yet' : 'No doctors found'} sub={f === 'recent' ? 'Doctors you visit will appear here.' : 'Try the full list.'} /></Card>}
  </div>
}

export default function Home() {
  const [d, setD] = useState(null); const [appts, setAppts] = useState([])
  useEffect(() => { api('/dashboard/patient').then(setD).catch(() => {}); api('/appointments?upcoming=true').then(r => setAppts(r.slice(0, 3))).catch(() => {}) }, [])
  return (
    <div>
      <div className="hero-gradient mb-5 rounded-2xl p-6 text-white shadow-lift md:p-7 [&_h1]:text-white [&_p]:text-white/80 [&_div]:!mb-0">
        <PageHead title="Good day — let's get you care" sub="Find, book and manage visits." />
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        <Card className="md:col-span-2 bg-gradient-to-br from-teal-deep to-teal text-white border-0">
          <div className="text-xs font-bold opacity-70">NEXT APPOINTMENT</div>
          {d?.upcoming ? <div className="mt-1"><div className="text-xl font-bold">{d.upcoming.doctor}</div><div className="opacity-80 text-sm">{new Date(d.upcoming.starts_at).toLocaleString()} · <Pill value={d.upcoming.status} /></div>
            <Link to={`/app/appointments/${d.upcoming.id}`} className="inline-block mt-3 bg-white text-teal-deep font-semibold text-sm rounded-xl px-4 py-2">View details</Link></div>
          : <div className="mt-1">No upcoming visits. <Link to="/app/book" className="underline font-semibold">Book a visit</Link> to get started.</div>}
        </Card>
        <Card><div className="text-xs font-bold text-ink-soft">CARE SUMMARY</div>
          <div className="text-3xl font-bold mt-1">{d?.total ?? '–'}</div><div className="text-sm text-ink-soft">total visits</div>
          <div className="mt-2 text-sm">Questionnaires due: <b>{d?.questionnaires_due ?? 0}</b></div>
          <Link to="/app/book" className="btn-primary w-full mt-4 text-center text-sm">Book visit</Link></Card>
      </div>
      <div className="grid md:grid-cols-2 gap-4 mt-4">
        <Card><div className="font-bold mb-2">Upcoming</div>{appts.length ? appts.map(a => <Link key={a.id} to={`/app/appointments/${a.id}`} className="flex justify-between py-2 border-t border-slate-100 text-sm"><span>{a.doctor_name} · {new Date(a.starts_at).toLocaleString()}</span><Pill value={a.status} /></Link>) : <Empty title="Nothing scheduled" sub="Your visits will appear here." />}</Card>
        <Card><div className="font-bold mb-2">Quick actions</div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <Link to="/app/book" className="btn-primary text-center">Book visit</Link>
            <Link to="/app/hospitals" className="btn-ghost text-center">Hospitals</Link>
            <Link to="/app/doctors" className="btn-ghost text-center">Find doctors</Link>
            <Link to="/app/questionnaires" className="btn-ghost text-center">Questionnaires</Link>
          </div></Card>
      </div>
      <div className="mt-6"><div className="mb-3 font-display text-xl font-semibold">Doctors for you</div><DoctorSpotlight /></div>
    </div>
  )
}
