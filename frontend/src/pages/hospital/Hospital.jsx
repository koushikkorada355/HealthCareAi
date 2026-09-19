import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client.js'
import { Card, PageHead, Pill, Avatar, Empty } from '../../components/ui.jsx'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'

function useHid() { const [me, setMe] = useState(null); useEffect(() => { api('/auth/me').then(setMe).catch(() => {}) }, []); return me?.hospital_id }

export function Dash() {
  const hid = useHid(); const [d, setD] = useState(null)
  useEffect(() => { if (hid) api(`/dashboard/hospital?hospital_id=${hid}`).then(setD).catch(() => {}) }, [hid])
  const cards = [['Appointments', d?.appointments], ['Confirmed', d?.confirmed], ['Doctors', d?.doctors], ['AI-booked', d?.ai_booked], ['AI conversations', d?.ai_conversations], ['Cancelled', d?.cancelled], ['Open reconciliation', d?.reconciliation_open], ['EHR risk', d?.ehr_ops_failed]]
  return <div><PageHead title="Hospital overview" sub="Bookings, capacity, questionnaires, AI-driven demand, integration risk." />
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">{cards.map(([l, v]) => <Card key={l}><div className="text-xs font-bold text-ink-soft">{l.toUpperCase()}</div><div className="text-3xl font-bold">{v ?? '–'}</div></Card>)}</div>
    {Number(d?.reconciliation_open) > 0 && <Card className="mt-4 !border-red-200"><b className="text-crit">{d.reconciliation_open} reconciliation(s) need attention.</b> <Link to="/hospital/integrations" className="text-teal font-semibold text-sm ml-2">Open integration log →</Link></Card>}
    <div className="grid md:grid-cols-2 gap-4 mt-4">
      <Card><div className="font-bold mb-2">EHR risk</div><div className="text-sm">Failed/unknown ops: <b>{d?.ehr_ops_failed ?? 0}</b></div><div className="text-sm">Questionnaires pending: <b>{d?.questionnaires_pending ?? 0}</b></div></Card>
      <Card><div className="font-bold mb-2">Shortcuts</div><div className="flex flex-wrap gap-2 text-sm"><Link to="/hospital/doctors" className="btn-ghost">Doctors</Link><Link to="/hospital/appointments" className="btn-ghost">Appointments</Link><Link to="/hospital/questionnaires" className="btn-ghost">Questionnaires</Link><Link to="/hospital/ai" className="btn-ghost">AI activity</Link></div></Card>
    </div></div>
}
export function Doctors() {
  const hid = useHid(); const [rows, setRows] = useState([]); const [f, setF] = useState({ name: '', specialty_id: '', email: '' }); const [specs, setSpecs] = useState([])
  const load = () => hid && api(`/doctors?hospital_id=${hid}`).then(setRows).catch(() => {})
  useEffect(() => { load(); if (hid) api(`/hospitals/${hid}/specialties`).then(setSpecs).catch(() => {}) }, [hid])
  return <div><PageHead title="Doctors" sub="Lifecycle: invited → active → inactive/suspended." right={<span className="text-sm text-ink-soft">{rows.length} doctors</span>} />
    <div className="grid md:grid-cols-3 gap-4">
      <div className="md:col-span-2 space-y-3">{rows.map(d => <Card key={d.id} className="flex items-center gap-4"><Avatar name={d.name} size={48} photo={d.photo_url} seed={d.id} plain={false} /><div className="flex-1"><div className="font-bold">{d.name}</div><div className="text-sm text-ink-soft">{d.specialty} · {d.experience_years}y · ★ {d.rating}</div></div><Pill value={d.status} /><Link to={`/hospital/doctors/${d.id}`} className="btn-ghost text-xs">Manage</Link></Card>)}</div>
      <Card><div className="font-bold mb-2">Add doctor</div>
        <input className="input mb-2" placeholder="Name" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} />
        <select className="input mb-2" value={f.specialty_id} onChange={e => setF({ ...f, specialty_id: e.target.value })}><option value="">Specialty…</option>{specs.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <input className="input mb-2" placeholder="Login email (optional)" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} />
        <button className="btn-primary w-full text-sm" onClick={async () => { await api('/doctors', { method: 'POST', body: { hospital_id: hid, name: f.name, specialty_id: f.specialty_id ? Number(f.specialty_id) : null, email: f.email } }); setF({ name: '', specialty_id: '', email: '' }); load() }}>Create + provision calendar</button></Card>
    </div></div>
}
export function DoctorDetail() {
  const { id } = useParams()
  const [d, setD] = useState(null)
  useEffect(() => { api(`/doctors/${id}`).then(setD).catch(() => {}) }, [id])
  if (!d) return <div className="p-8">Loading…</div>
  return <div><PageHead title={d.name} right={<select className="input !w-auto" value={d.status} onChange={async e => { await api(`/doctors/${id}`, { method: 'PATCH', body: { status: e.target.value } }); setD({ ...d, status: e.target.value }) }}>{['invited', 'active', 'inactive', 'suspended'].map(s => <option key={s}>{s}</option>)}</select>} />
    <div className="flex items-center gap-4 mb-4"><Avatar name={d.name} size={64} photo={d.photo_url} seed={d.id} plain={false} /><div className="text-sm text-ink-soft">Auto Unsplash photo — no upload needed.</div></div>
    <div className="grid md:grid-cols-2 gap-4"><Card><div className="text-sm space-y-1"><div><b>Specialty:</b> {d.specialty}</div><div><b>External provider ID:</b> <code>{d.external_provider_id}</code></div><div><b>Duration:</b> {d.duration_minutes} min</div></div></Card>
    <Card><div className="font-bold mb-2">Calendars</div>{d.calendars?.map(c => <div key={c.id} className="text-sm py-1.5 border-t border-slate-100">{c.name} · {c.is_active ? 'active' : 'paused'}</div>)}</Card></div></div>
}
export function Schedules() {
  const hid = useHid(); const [docs, setDocs] = useState([]); const [did, setDid] = useState(''); const [slots, setSlots] = useState([])
  useEffect(() => { if (hid) api(`/doctors?hospital_id=${hid}`).then(r => { setDocs(r); if (r[0]) setDid(r[0].id) }).catch(() => {}) }, [hid])
  useEffect(() => { if (did) api(`/availability?doctor_id=${did}&days_ahead=7`).then(r => setSlots(r.slots)).catch(() => {}) }, [did])
  return <div><PageHead title="Schedules & availability" sub="Computed live by the scheduling engine." />
    <select className="input max-w-sm mb-3" value={did} onChange={e => setDid(e.target.value)}>{docs.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
    <Card><div className="font-bold mb-2">{slots.length} open slots (7 days)</div>{slots.slice(0, 20).map(s => <div key={`${s.calendar_id}-${s.starts_at}`} className="text-sm py-1.5 border-t border-slate-100">{new Date(s.starts_at).toLocaleString()}</div>)}{!slots.length && <Empty title="Fully booked or blocked" />}</Card></div>
}
export function Appointments() {
  const [rows, setRows] = useState([]); const [f, setF] = useState('all'); const [aiOnly, setAiOnly] = useState(false)
  useEffect(() => { api('/appointments').then(setRows).catch(() => {}) }, [])
  const list = rows.filter(a => (f === 'all' || a.status === f) && (!aiOnly || a.via_ai))
  return <div><PageHead title="Appointments" sub="Every booking with verification state — including AI-driven ones." right={<span className="flex gap-2"><button type="button" onClick={() => setAiOnly(!aiOnly)} className={aiOnly ? 'btn-primary text-xs' : 'btn-ghost text-xs'}>{aiOnly ? '✓ AI-booked only' : 'AI-booked only'}</button><select className="input !w-auto text-sm" aria-label="Filter by status" value={f} onChange={e => setF(e.target.value)}>{['all', 'confirmed', 'pending', 'rescheduled', 'cancelled', 'completed', 'no_show', 'failed', 'reconciliation_required'].map(s => <option key={s} value={s}>{s === 'all' ? 'All statuses' : s}</option>)}</select></span>} />
    <Card>{list.length ? list.map(a => <div key={a.id} className="flex flex-wrap justify-between gap-2 text-sm py-2.5 border-t border-slate-100"><span><b>#{a.id}</b> {new Date(a.starts_at).toLocaleString()} · {a.doctor_name} · {a.patient_name}</span><span className="flex gap-1.5">{a.via_ai && <span className="pill bg-violet-50 text-violet-700">via AI</span>}<Pill value={a.status} /><Pill value={a.integration_status} /></span></div>) : <Empty title="No appointments match" />}</Card></div>
}
export function Questionnaires() {
  const hid = useHid(); const [rows, setRows] = useState([]); const [t, setT] = useState('')
  useEffect(() => { if (hid) api(`/questionnaires?hospital_id=${hid}`).then(setRows).catch(() => {}) }, [hid])
  return <div><PageHead title="Questionnaires" sub="Admin-approved pre-visit sets. AI collects answers conversationally." />
    <Card className="mb-4"><div className="font-bold mb-2">Builder (quick add)</div><div className="flex gap-2"><input className="input" placeholder="Title, e.g. Diabetes pre-visit" value={t} onChange={e => setT(e.target.value)} /><button className="btn-primary text-sm" onClick={async () => { await api('/questionnaires', { method: 'POST', body: { hospital_id: hid, title: t, schema: [{ id: 'q1', label: 'Reason for visit', type: 'long_text', required: true }] } }); setT(''); api(`/questionnaires?hospital_id=${hid}`).then(setRows) }}>Add</button></div></Card>
    {rows.map(q => <Card key={q.id} className="mb-3"><div className="font-bold">{q.title}</div><div className="text-sm text-ink-soft">{q.description} · {q.schema?.length || 0} questions</div><pre className="text-xs bg-slate-50 rounded-xl p-2 mt-2 overflow-auto">{JSON.stringify(q.schema, null, 1).slice(0, 600)}</pre></Card>)}</div>
}
export function AIActivity() {
  const [rows, setRows] = useState([]); const [execs, setExecs] = useState([]); const [open, setOpen] = useState(null); const [detail, setDetail] = useState(null)
  useEffect(() => { api('/ai/conversations').then(setRows).catch(() => {}); api('/mcp/executions').then(setExecs).catch(() => {}) }, [])
  const toggle = async (c) => {
    if (open === c.id) { setOpen(null); setDetail(null); return }
    setOpen(c.id); setDetail(null)
    try { setDetail(await api(`/ai/conversations/${c.id}`)) } catch { setDetail({ messages: [], capabilities: [], error: 'Could not load conversation.' }) }
  }
  return <div><PageHead title="AI activity" sub="Conversations + every capability execution (never direct DB/EHR). Click a conversation to inspect what the AI did." />
    <div className="grid md:grid-cols-2 gap-4">
      <Card><div className="font-bold mb-2">Conversations</div>{rows.map(c => (
        <div key={c.id} className="border-t border-slate-100">
          <button type="button" onClick={() => toggle(c)} className="flex w-full justify-between py-2 text-sm text-left hover:text-brand-deep"><span>#{c.id} · {c.channel} · {c.messages} msgs · <code>{c.correlation_id}</code></span><span>{open === c.id ? '▾' : '▸'}</span></button>
          {open === c.id && <div className="mb-2 rounded-xl bg-slate-50 p-3">
            {!detail ? <div className="skeleton h-10 rounded-lg" /> : detail.error ? <div className="text-sm text-crit">{detail.error}</div> : <>
              {detail.messages?.slice(-8).map((m, i) => <div key={i} className={`mb-1.5 max-w-[95%] rounded-xl px-3 py-1.5 text-xs ${m.role === 'user' ? 'ml-auto bg-brand text-white' : 'bg-white border border-slate-200'}`}>{m.content?.slice(0, 300)}</div>)}
              {!!detail.capabilities?.length && <div className="mt-2 text-xs font-bold text-ink-soft">CAPABILITIES USED</div>}
              {detail.capabilities?.map((x, i) => <div key={i} className="flex justify-between text-xs py-1 border-t border-slate-200"><code>{x.name}</code><Pill value={x.status} /></div>)}
            </>}
          </div>}
        </div>))}{!rows.length && <Empty title="No conversations yet" />}</Card>
      <Card><div className="font-bold mb-2">Capability executions</div>{execs.slice(0, 30).map(e => <div key={e.id} className="text-sm py-1.5 border-t border-slate-100 flex justify-between"><span><code>{e.name}</code></span><Pill value={e.status} /></div>)}</Card>
    </div></div>
}
export function Integrations() {
  const [ops, setOps] = useState([]); const [conns, setConns] = useState([]); const [recon, setRecon] = useState([])
  const load = () => { api('/integrations/operations').then(setOps).catch(() => {}); api('/integrations/connections').then(setConns).catch(() => {}); api('/reconciliation').then(setRecon).catch(() => {}) }
  useEffect(load, [])
  return <div><PageHead title="Integrations" sub="Every EHR call verified; unknowns recovered without duplicates." right={<button className="btn-ghost text-sm" onClick={load}>Refresh</button>} />
    {recon.filter(r => r.status === 'open').map(r => <Card key={r.id} className="mb-3 !border-red-200"><div className="text-sm"><b className="text-crit">Reconciliation #{r.id}</b> · appt #{r.appointment_id} · {r.issue} · <code>{r.correlation_id}</code></div><button className="btn-primary text-xs mt-2" onClick={async () => { await api(`/appointments/${r.appointment_id}/retry-sync`, { method: 'POST', body: {} }); load() }}>Probe EHR + sync now</button></Card>)}
    <div className="grid md:grid-cols-2 gap-4">
      <Card><div className="font-bold mb-2">Connections</div>{conns.map(c => <div key={c.id} className="text-sm py-1.5 border-t border-slate-100 flex justify-between"><span>#{c.hospital_id} · {c.vendor} · {c.base_url}</span><Pill value={c.status} /></div>)}</Card>
      <Card><div className="font-bold mb-2">Operations</div>{ops.slice(0, 30).map(o => <div key={o.id} className="text-sm py-1.5 border-t border-slate-100"><div className="flex justify-between"><span><code>{o.kind}</code> appt #{o.ref_id}</span><Pill value={o.status} /></div><div className="text-xs text-ink-soft font-mono">{o.correlation_id} · {o.error?.slice(0, 120)}</div></div>)}</Card>
    </div></div>
}
export function Workflows() {
  const [ws, setWs] = useState([]); const [ex, setEx] = useState([])
  useEffect(() => { api('/workflows').then(setWs).catch(() => {}); api('/workflow-executions').then(setEx).catch(() => {}) }, [])
  return <div><PageHead title="Workflows" /><div className="grid md:grid-cols-2 gap-4">
    <Card><div className="font-bold mb-2">Triggers</div>{ws.map(w => <div key={w.id} className="text-sm py-2 border-t border-slate-100"><b>{w.name}</b><div className="text-xs text-ink-soft font-mono">on {w.trigger_event} · {w.steps?.length} steps</div></div>)}</Card>
    <Card><div className="font-bold mb-2">Executions</div>{ex.slice(0, 30).map(e => <div key={e.id} className="text-sm py-1.5 border-t border-slate-100 flex justify-between"><span>wf #{e.workflow_id} · <code>{e.correlation_id}</code></span><Pill value={e.status} /></div>)}</Card></div></div>
}
export function Notifications() {
  const [rows, setRows] = useState([])
  useEffect(() => { api('/notifications').then(setRows).catch(() => {}) }, [])
  return <div><PageHead title="Notifications" /><Card>{rows.map(n => <div key={n.id} className="text-sm py-2 border-t border-slate-100"><b>{n.title}</b> <span className="text-ink-soft">· {n.kind} · {n.channel}</span><div className="text-ink-soft">{n.body?.slice(0, 140)}</div></div>)}</Card></div>
}
export function Analytics() {
  const [d, setD] = useState(null)
  useEffect(() => { api('/analytics/overview').then(setD).catch(() => {}) }, [])
  const ap = Object.entries(d?.appointments_by_status || {}).map(([name, value]) => ({ name, value }))
  return <div><PageHead title="Analytics" /><div className="grid md:grid-cols-2 gap-4">
    <Card><div className="font-bold mb-2">Appointments by status</div><ResponsiveContainer width="100%" height={240}><BarChart data={ap}><XAxis dataKey="name" fontSize={11} /><YAxis /><Tooltip /><Bar dataKey="value" fill="#0E7C7B" radius={6} /></BarChart></ResponsiveContainer></Card>
    <Card><div className="font-bold mb-2">EHR operations</div><ResponsiveContainer width="100%" height={240}><PieChart><Pie data={Object.entries(d?.ehr_ops || {}).map(([name, value]) => ({ name, value }))} dataKey="value" nameKey="name" outerRadius={90} label>{[0, 1, 2, 3].map(i => <Cell key={i} fill={['#0E7C7B', '#1B9E6B', '#C98A12', '#C0392B'][i % 4]} />)}</Pie><Tooltip /></PieChart></ResponsiveContainer></Card></div></div>
}
export function Audit() {
  const [rows, setRows] = useState([])
  useEffect(() => { api('/audit').then(setRows).catch(() => {}); }, [])
  return <div><PageHead title="Audit log" /><Card>{rows.slice(0, 80).map(a => <div key={a.id} className="text-sm py-1.5 border-t border-slate-100 font-mono text-xs">{a.at?.slice(0, 19)} · {a.action} · {a.entity} #{a.entity_id} · {a.correlation_id}</div>)}</Card></div>
}
