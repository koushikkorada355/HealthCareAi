import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client.js'
import { Card, PageHead, Pill, Empty } from '../../components/ui.jsx'

export default function Home() {
  const [d, setD] = useState(null); const [appts, setAppts] = useState([])
  useEffect(() => { api('/dashboard/patient').then(setD).catch(() => {}); api('/appointments?upcoming=true').then(r => setAppts(r.slice(0, 3))).catch(() => {}) }, [])
  return (
    <div>
      <div className="hero-gradient mb-5 rounded-2xl p-6 text-white shadow-lift md:p-7 [&_h1]:text-white [&_p]:text-white/80 [&_div]:!mb-0">
        <PageHead title="Good day — let's get you care" sub="One assistant for finding, booking and managing visits." />
      </div>
      <div className="grid md:grid-cols-3 gap-4">
        <Card className="md:col-span-2 bg-gradient-to-br from-teal-deep to-teal text-white border-0">
          <div className="text-xs font-bold opacity-70">NEXT APPOINTMENT</div>
          {d?.upcoming ? <div className="mt-1"><div className="text-xl font-bold">{d.upcoming.doctor}</div><div className="opacity-80 text-sm">{new Date(d.upcoming.starts_at).toLocaleString()} · <Pill value={d.upcoming.status} /></div>
            <Link to={`/app/appointments/${d.upcoming.id}`} className="inline-block mt-3 bg-white text-teal-deep font-semibold text-sm rounded-xl px-4 py-2">View details</Link></div>
          : <div className="mt-1">No upcoming visits. <Link to="/app/assistant" className="underline font-semibold">Ask the assistant</Link> to book one.</div>}
        </Card>
        <Card><div className="text-xs font-bold text-ink-soft">CARE SUMMARY</div>
          <div className="text-3xl font-bold mt-1">{d?.total ?? '–'}</div><div className="text-sm text-ink-soft">total visits</div>
          <div className="mt-2 text-sm">Questionnaires due: <b>{d?.questionnaires_due ?? 0}</b></div>
          <Link to="/app/assistant" className="btn-primary w-full mt-4 text-center text-sm">Ask AI assistant</Link></Card>
      </div>
      <div className="grid md:grid-cols-2 gap-4 mt-4">
        <Card><div className="font-bold mb-2">Upcoming</div>{appts.length ? appts.map(a => <Link key={a.id} to={`/app/appointments/${a.id}`} className="flex justify-between py-2 border-t border-slate-100 text-sm"><span>{a.doctor_name} · {new Date(a.starts_at).toLocaleString()}</span><Pill value={a.status} /></Link>) : <Empty title="Nothing scheduled" sub="Your visits will appear here." />}</Card>
        <Card><div className="font-bold mb-2">Quick actions</div>
          <div className="grid grid-cols-2 gap-2 text-sm">
            <Link to="/app/book" className="btn-primary text-center">Book visit</Link>
            <Link to="/app/voice" className="btn-ghost text-center">Voice booking</Link>
            <Link to="/app/doctors" className="btn-ghost text-center">Find doctors</Link>
            <Link to="/app/hospitals" className="btn-ghost text-center">Hospitals</Link>
            <Link to="/app/questionnaires" className="btn-ghost text-center col-span-2">Questionnaires</Link>
          </div></Card>
      </div>
    </div>
  )
}
