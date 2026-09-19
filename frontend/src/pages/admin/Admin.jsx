import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client.js'
import { Card, PageHead, Pill, Empty } from '../../components/ui.jsx'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts'

export function Dash() {
  const [d, setD] = useState(null)
  useEffect(() => { api('/dashboard/platform').then(setD).catch(() => {}) }, [])
  const capTotal = Number(d?.cap_success || 0) + Number(d?.cap_failed || 0)
  const capRate = capTotal ? `${Math.round((Number(d.cap_success) / capTotal) * 100)}%` : '–'
  const kpis = [['Total hospitals', d?.hospitals], ['Pending applications', d?.applications_pending], ['Under review', d?.hospitals_under_review], ['Approved', d?.hospitals_approved], ['Rejected', d?.hospitals_rejected], ['Correction required', d?.hospitals_corrections], ['Suspended', d?.hospitals_suspended], ['Draft', d?.hospitals_draft], ['Doctors', d?.doctors], ['Patients', d?.patients], ['Appointments', d?.appointments], ['AI conversations', d?.ai_conversations], ['Capability success', capRate], ['Cap failed', d?.cap_failed]]
  return <div><PageHead title="Platform operations" sub="Hospitals by lifecycle status and review queue — one wall." />
    <div className="grid md:grid-cols-4 gap-4">{kpis.map(([l, v]) => <Card key={l}><div className="text-xs font-bold text-ink-soft">{l.toUpperCase()}</div><div className="text-3xl font-bold">{v ?? '–'}</div></Card>)}</div>
    <div className="grid md:grid-cols-1 gap-4 mt-4">
      <Card><div className="font-bold">Review queue</div><div className="text-sm mt-1">Submitted: <b>{d?.hospitals_submitted ?? 0}</b> · Under review: <b>{d?.hospitals_under_review ?? 0}</b> · Corrections: <b>{d?.hospitals_corrections ?? 0}</b></div><Link to="/admin/applications" className="btn-primary text-sm mt-3 inline-block">Open review queue</Link></Card>
    </div></div>
}
export function Applications() {
  const [rows, setRows] = useState([]); const [f, setF] = useState('submitted'); const [note, setNote] = useState(''); const [acting, setActing] = useState(null); const [msg, setMsg] = useState('')
  const load = (status = f) => api(`/hospitals?status=${status === 'all' ? '' : status}`).then(setRows).catch(() => {})
  useEffect(() => { load() }, [f])
  // Backend statuses differ from action names: follow the item to its new
  // status filter so the card stays visible instead of the list going blank.
  const NEXT_FILTER = { under_review: 'under_review', approve: 'approved', reject: 'rejected', corrections: 'corrections_requested', suspend: 'suspended', reactivate: 'approved' }
  const act = async (id, action, name) => {
    setActing(`${id}-${action}`); setMsg('')
    try {
      const r = await api(`/hospitals/${id}/review`, { method: 'POST', body: { action, note } })
      setNote(''); const next = NEXT_FILTER[action] || f; setF(next)
      if (next !== f) { setRows([]); await api(`/hospitals?status=${next === 'all' ? '' : next}`).then(setRows).catch(() => {}) }
      else load()
      setMsg(`${name || `#${id}`} → ${r.status}`)
    }
    catch (e) { setMsg(`Could not ${action}: ${e.message}`) } finally { setActing(null) }
  }
  const ACTIONS = ['under_review', 'approve', 'reject', 'corrections', 'suspend', 'reactivate']
  const STATUSES = ['submitted', 'under_review', 'corrections_requested', 'approved', 'rejected', 'suspended', 'draft', 'all']
  return <div><PageHead title="Hospital applications" sub="Pending Review: new → under review → correction required. Open any card for the full file." right={<select className="input !w-auto" aria-label="Filter by status" value={f} onChange={e => { setF(e.target.value); setMsg('') }}>{STATUSES.map(s => <option key={s}>{s}</option>)}</select>} />
    <Card className="mb-3"><label htmlFor="app-note" className="text-xs font-bold">REVIEW NOTE (attached to approve / reject / corrections…)</label>
      <input id="app-note" className="input mt-1" placeholder="e.g. Verified license, looks good" value={note} onChange={e => setNote(e.target.value)} /></Card>
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    {rows.map(h => <Card key={h.id} className="mb-3 flex flex-wrap items-center gap-3"><div className="flex-1 min-w-[200px]"><div className="font-bold">{h.name}</div><div className="text-sm text-ink-soft">{h.city} · {h.contact_email} · {h.doctor_count ?? 0} doctors · submitted {h.created_at?.slice(0, 10) || '—'}</div>{h.review_notes && <div className="text-xs text-amber-700 mt-1">Note: {h.review_notes}</div>}</div><Pill value={h.status} />
      <Link to={`/admin/applications/${h.id}`} className="btn-primary text-xs">Open / review</Link>
      <div className="flex flex-wrap gap-1.5">{ACTIONS.map(a => <button key={a} type="button" disabled={!!acting} onClick={() => act(h.id, a, h.name)} className="btn-ghost text-xs">{acting === `${h.id}-${a}` ? '…' : a.replace('_', ' ')}</button>)}</div></Card>)}
    {!rows.length && !acting && <Card><Empty title={msg ? 'Moved to another status' : 'Empty queue'} sub={msg || 'New applications appear here. Use the status filter above.'} /></Card>}</div>
}
export function ApplicationDetail() {
  const { id } = useParams()
  const [h, setH] = useState(null); const [hist, setHist] = useState([]); const [note, setNote] = useState(''); const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false)
  const load = () => { api(`/hospitals/${id}`).then(setH).catch(() => setMsg('Could not load application.')); api(`/hospitals/${id}/history`).then(setHist).catch(() => {}) }
  useEffect(load, [id])
  const act = async (action) => {
    setBusy(true); setMsg('')
    try { const r = await api(`/hospitals/${id}/review`, { method: 'POST', body: { action, note } }); setNote(''); load(); setMsg(`Status → ${r.status}`) }
    catch (e) { setMsg(`Could not ${action}: ${e.message}`) } finally { setBusy(false) }
  }
  if (!h) return <div className="p-8">{msg ? <Card><Empty title="Could not load application" sub={msg} /><Link to="/admin/applications" className="btn-ghost text-sm mt-3 inline-block">← Back to review queue</Link></Card> : 'Loading…'}</div>
  const ACTIONS = ['under_review', 'approve', 'reject', 'corrections', 'suspend', 'reactivate']
  return <div><PageHead title={h.name} sub={`Application ${h.slug} · submitted ${h.created_at?.slice(0, 10) || '—'}`} right={<Pill value={h.status} />} />
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    <div className="grid md:grid-cols-2 gap-4">
      <Card><div className="font-bold mb-2">Organization</div><div className="text-sm space-y-1"><div><b>Address:</b> {h.address} · {h.city}</div><div><b>Contact:</b> {h.contact_email} · {h.phone}</div><div><b>Services:</b> {h.services}</div><div><b>Hours:</b> <code className="text-xs">{h.operating_hours}</code></div><div><b>Doctors:</b> {h.doctor_count} active · <b>Completed visits:</b> {h.completed_visits}</div></div></Card>
      <Card><div className="font-bold mb-2">Systems & admins</div><div className="text-sm space-y-1"><div><b>EHR vendor:</b> {h.ehr_vendor} · <b>Facility:</b> <code className="text-xs">{h.external_facility_id}</code></div><div><b>Connections:</b> {(h.connections || []).map(c => `${c.vendor}@${c.base_url} (${c.status})`).join(', ') || '—'}</div><div><b>Admins:</b> {(h.admins || []).map(a => `${a.full_name} <${a.email}>`).join(', ') || '—'}</div><div><b>Departments:</b> {(h.departments || []).map(d => d.name).join(', ') || '—'}</div><div><b>Specialties:</b> {(h.specialties || []).map(s => s.name).join(', ') || '—'}</div></div></Card>
    </div>
    <Card className="mt-4"><div className="font-bold mb-2">Review note</div><input className="input" placeholder="e.g. Verified license, request fire NOC…" value={note} onChange={e => setNote(e.target.value)} /><div className="flex flex-wrap gap-1.5 mt-2">{ACTIONS.map(a => <button key={a} type="button" disabled={busy} onClick={() => act(a)} className="btn-ghost text-xs">{a.replace('_', ' ')}</button>)}</div>{h.review_notes && <div className="text-xs text-amber-700 mt-2">Last note: {h.review_notes}</div>}</Card>
    <Card className="mt-4"><div className="font-bold mb-2">Status timeline</div>{hist.length ? hist.map(e => <div key={e.id} className="text-xs font-mono py-1.5 border-t border-slate-100">{e.at?.slice(0, 19)} · {e.action} · user #{e.actor_user_id ?? '—'} · {e.correlation_id}</div>) : <div className="text-sm text-ink-soft">No recorded actions yet.</div>}</Card>
  </div>
}
export function TablePage({ title, path, cols }) {
  const [rows, setRows] = useState([])
  useEffect(() => { api(path).then(r => setRows(Array.isArray(r) ? r : [])).catch(() => {}) }, [path])
  return <div><PageHead title={title} right={<span className="text-sm text-ink-soft">{rows.length} rows</span>} />
    <Card className="overflow-auto"><table className="tbl w-full min-w-[640px]"><thead><tr>{cols.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>
      {rows.slice(0, 100).map((r) => <tr key={r.id ?? JSON.stringify(r).slice(0, 40)}>{cols.map(c => <td key={c} className="pr-4 max-w-[280px] truncate">{typeof r[c] === 'object' ? JSON.stringify(r[c])?.slice(0, 80) : String(r[c] ?? '—')}</td>)}</tr>)}</tbody></table></Card></div>
}
export function AIActivity() {
  const [c, setC] = useState([]); const [e, setE] = useState([]); const [evals, setEvals] = useState([])
  const [open, setOpen] = useState(null); const [detail, setDetail] = useState(null)
  useEffect(() => { api('/ai/conversations').then(setC).catch(() => {}); api('/mcp/executions').then(setE).catch(() => {}); api('/ai/evaluation').then(setEvals).catch(() => {}) }, [])
  const toggle = async (x) => {
    if (open === x.id) { setOpen(null); setDetail(null); return }
    setOpen(x.id); setDetail(null)
    try { setDetail(await api(`/ai/conversations/${x.id}`)) } catch { setDetail({ messages: [], capabilities: [], error: 'Could not load conversation.' }) }
  }
  return <div><PageHead title="AI activity & evaluation" sub="Click a conversation to inspect exactly what the AI understood and which capabilities it ran." />
    {!!evals.length && <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-4">{evals.slice(0, 4).map(v => <Card key={v.id}><div className="text-xs font-bold text-ink-soft">{String(v.metric).toUpperCase()}</div><div className="text-3xl font-bold">{typeof v.score === 'number' ? `${Math.round(v.score * 100)}%` : v.score}</div></Card>)}</div>}
    <div className="grid md:grid-cols-2 gap-4"><Card><div className="font-bold mb-2">Conversations ({c.length})</div>{c.slice(0, 20).map(x => (
      <div key={x.id} className="border-t border-slate-100">
        <button type="button" onClick={() => toggle(x)} className="flex w-full justify-between py-1.5 text-sm text-left hover:text-brand-deep"><span>#{x.id} · {x.channel} · {x.messages} msgs</span><span>{open === x.id ? '▾' : '▸'}</span></button>
        {open === x.id && <div className="mb-2 rounded-xl bg-slate-50 p-3">
          {!detail ? <div className="skeleton h-10 rounded-lg" /> : detail.error ? <div className="text-sm text-crit">{detail.error}</div> : <>
            {detail.messages?.slice(-8).map((m, i) => <div key={i} className={`mb-1.5 max-w-[95%] rounded-xl px-3 py-1.5 text-xs ${m.role === 'user' ? 'ml-auto bg-brand text-white' : 'bg-white border border-slate-200'}`}>{m.content?.slice(0, 300)}</div>)}
            {!!detail.capabilities?.length && <div className="mt-2 text-xs font-bold text-ink-soft">CAPABILITIES USED</div>}
            {detail.capabilities?.map((cp, i) => <div key={i} className="flex justify-between text-xs py-1 border-t border-slate-200"><code>{cp.name}</code><Pill value={cp.status} /></div>)}
          </>}
        </div>}
      </div>))}</Card>
    <Card><div className="font-bold mb-2">Tool calls</div>{e.slice(0, 30).map(x => <div key={x.id} className="text-sm py-1 border-t border-slate-100 flex justify-between"><code>{x.name}</code><Pill value={x.status} /></div>)}</Card></div></div>
}
export function Analytics() {
  const [d, setD] = useState(null)
  useEffect(() => { api('/analytics/overview').then(setD).catch(() => {}) }, [])
  const ap = Object.entries(d?.appointments_by_status || {}).map(([name, value]) => ({ name, value }))
  return <div><PageHead title="Analytics" /><Card><div className="font-bold mb-2">Appointments by status</div>
    <ResponsiveContainer width="100%" height={280}><BarChart data={ap}><XAxis dataKey="name" fontSize={11} /><YAxis /><Tooltip /><Bar dataKey="value" fill="#0E7C7B" radius={6} /></BarChart></ResponsiveContainer></Card></div>
}
export function OpsHealth() {
  const [rows, setRows] = useState([])
  useEffect(() => { api('/ops/events').then(setRows).catch(() => {}) }, [])
  return <div><PageHead title="Operational health" /><Card>{rows.slice(0, 80).map(e => <div key={e.id} className="text-xs font-mono py-1.5 border-t border-slate-100">[{e.severity}] {e.kind} — {e.message?.slice(0, 140)} · {e.correlation_id}</div>)}</Card></div>
}
