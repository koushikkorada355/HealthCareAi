import React, { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client.js'
import { Card, PageHead, Pill, Empty } from '../../components/ui.jsx'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, LineChart, Line } from 'recharts'

export function Dash() {
  const [d, setD] = useState(null)
  useEffect(() => { api('/dashboard/platform').then(setD).catch(() => {}) }, [])
  const capTotal = Number(d?.cap_success || 0) + Number(d?.cap_failed || 0)
  const capRate = capTotal ? `${Math.round((Number(d.cap_success) / capTotal) * 100)}%` : '–'
  const kpis = [['Hospitals', d?.hospitals], ['Pending applications', d?.applications_pending], ['Doctors', d?.doctors], ['Patients', d?.patients], ['Appointments', d?.appointments], ['AI conversations', d?.ai_conversations], ['Capability success', capRate], ['Cap failed', d?.cap_failed]]
  return <div><PageHead title="Platform operations" sub="Health, AI, integrations, reconciliation — one wall." />
    <div className="grid md:grid-cols-4 gap-4">{kpis.map(([l, v]) => <Card key={l}><div className="text-xs font-bold text-ink-soft">{l.toUpperCase()}</div><div className="text-3xl font-bold">{v ?? '–'}</div></Card>)}</div>
    <div className="grid md:grid-cols-2 gap-4 mt-4">
      <Card className={Number(d?.reconciliation_open) > 0 ? '!border-red-300' : ''}><div className="font-bold">Recovery queue</div><div className="text-sm mt-1">Open reconciliations: <b>{d?.reconciliation_open ?? 0}</b> · Unknown outcomes: <b>{d?.unknown_outcome ?? 0}</b></div><Link to="/admin/reconciliation" className="btn-primary text-sm mt-3 inline-block">Open failure/recovery view</Link></Card>
      <Card><div className="font-bold">Failure demo (1 click)</div><div className="text-sm text-ink-soft mt-1">Book with <code>simulate=timeout_after_create</code> via API or MCP, then watch probe → sync without duplicate here and in Integrations.</div><Link to="/admin/integrations" className="btn-ghost text-sm mt-3 inline-block">View integration chain</Link></Card>
    </div></div>
}
export function Applications() {
  const [rows, setRows] = useState([]); const [f, setF] = useState('submitted'); const [note, setNote] = useState(''); const [acting, setActing] = useState(null)
  const load = () => api(`/hospitals?status=${f === 'all' ? '' : f}`).then(setRows).catch(() => {})
  useEffect(load, [f])
  const act = async (id, action) => {
    setActing(`${id}-${action}`)
    try { await api(`/hospitals/${id}/review`, { method: 'POST', body: { action, note } }); setNote(''); load() }
    catch (e) { alert(`Could not ${action}: ${e.message}`) } finally { setActing(null) }
  }
  const ACTIONS = ['under_review', 'approve', 'reject', 'corrections', 'suspend', 'reactivate']
  return <div><PageHead title="Hospital applications" right={<select className="input !w-auto" aria-label="Filter by status" value={f} onChange={e => setF(e.target.value)}>{['submitted', 'under_review', 'approved', 'rejected', 'all'].map(s => <option key={s}>{s}</option>)}</select>} />
    <Card className="mb-3"><label htmlFor="app-note" className="text-xs font-bold">REVIEW NOTE (attached to approve / reject / corrections…)</label>
      <input id="app-note" className="input mt-1" placeholder="e.g. Verified license, looks good" value={note} onChange={e => setNote(e.target.value)} /></Card>
    {rows.map(h => <Card key={h.id} className="mb-3 flex flex-wrap items-center gap-3"><div className="flex-1 min-w-[200px]"><div className="font-bold">{h.name}</div><div className="text-sm text-ink-soft">{h.city} · {h.contact_email}</div></div><Pill value={h.status} />
      <div className="flex flex-wrap gap-1.5">{ACTIONS.map(a => <button key={a} type="button" disabled={!!acting} onClick={() => act(h.id, a)} className="btn-ghost text-xs">{acting === `${h.id}-${a}` ? '…' : a.replace('_', ' ')}</button>)}</div></Card>)}
    {!rows.length && <Card><Empty title="Empty queue" sub="New applications appear here." /></Card>}</div>
}
export function TablePage({ title, path, cols }) {
  const [rows, setRows] = useState([])
  useEffect(() => { api(path).then(r => setRows(Array.isArray(r) ? r : [])).catch(() => {}) }, [path])
  return <div><PageHead title={title} right={<span className="text-sm text-ink-soft">{rows.length} rows</span>} />
    <Card className="overflow-auto"><table className="tbl w-full min-w-[640px]"><thead><tr>{cols.map(c => <th key={c}>{c}</th>)}</tr></thead><tbody>
      {rows.slice(0, 100).map((r) => <tr key={r.id ?? JSON.stringify(r).slice(0, 40)}>{cols.map(c => <td key={c} className="pr-4 max-w-[280px] truncate">{typeof r[c] === 'object' ? JSON.stringify(r[c])?.slice(0, 80) : String(r[c] ?? '—')}</td>)}</tr>)}</tbody></table></Card></div>
}
export function Integrations() {
  const [ops, setOps] = useState([])
  useEffect(() => { api('/integrations/operations').then(setOps).catch(() => {}) }, [])
  return <div><PageHead title="Integration activity" sub="Create → verify → sync. Unknown outcomes probed, never blindly retried." />
    {ops.slice(0, 60).map(o => <Card key={o.id} className="mb-2"><div className="flex justify-between text-sm"><span><code>{o.kind}</code> · appt #{o.ref_id} · attempts {o.attempts}</span><Pill value={o.status} /></div><div className="text-xs font-mono text-ink-soft mt-1">corr {o.correlation_id} · {o.error?.slice(0, 200)}</div></Card>)}
    {!ops.length && <Card><Empty title="No operations yet" /></Card>}</div>
}
export function Reconciliation() {
  const [rows, setRows] = useState([])
  const load = () => api('/reconciliation').then(setRows).catch(() => {})
  useEffect(load, [])
  return <div><PageHead title="Reconciliation & recovery" sub="Timeout → query external → sync safely → no duplicates." right={<button className="btn-ghost text-sm" onClick={load}>Refresh</button>} />
    {rows.map(r => <Card key={r.id} className={`mb-3 ${r.status === 'open' ? '!border-red-300' : ''}`}><div className="flex flex-wrap items-center gap-2 text-sm"><b>#{r.id}</b><span>{r.issue}</span><span className="text-ink-soft">appt #{r.appointment_id}</span><Pill value={r.status} /><code className="text-xs">{r.correlation_id}</code></div>
      {r.status === 'open' && <div className="flex gap-2 mt-2"><button className="btn-primary text-xs" onClick={async () => { await api(`/appointments/${r.appointment_id}/retry-sync`, { method: 'POST', body: {} }); load() }}>Probe EHR + sync</button><button className="btn-ghost text-xs" onClick={async () => { await api(`/reconciliation/${r.id}/resolve`, { method: 'POST', body: { status: 'escalated', resolution: 'Escalated to ops queue' } }); load() }}>Escalate to human</button><button className="btn-ghost text-xs" onClick={async () => { await api(`/reconciliation/${r.id}/resolve`, { method: 'POST', body: { status: 'resolved', resolution: 'Manually verified' } }); load() }}>Mark resolved</button></div>}</Card>)}
    {!rows.length && <Card><Empty title="Queue clear" sub="Failures with unknown outcomes land here." /></Card>}</div>
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
