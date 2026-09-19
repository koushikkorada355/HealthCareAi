import React, { useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api } from '../../api/client.js'
import { useAuth } from '../../context/AuthContext.jsx'
import { Card, PageHead, Pill, Avatar, Empty } from '../../components/ui.jsx'

function AiBadge({ a }) {
  if (!a?.via_ai) return null
  return <span className="pill bg-violet-50 text-violet-700" title={a.conversation_id ? `AI conversation #${a.conversation_id}` : 'Booked through the AI assistant'}>via AI</span>
}

export function Dash() {
  const { user } = useAuth()
  const [d, setD] = useState(null); const [today, setToday] = useState([])
  useEffect(() => { api('/dashboard/doctor').then(setD).catch(() => {}); api('/appointments').then(r => setToday(r.slice(0, 8))).catch(() => {}) }, [])
  if (user && !user.doctor_id) return <div><PageHead title="Doctor dashboard" sub="Your hospital invite is pending." /><Card><Empty title="Awaiting hospital" sub="Share your login email with your hospital admin. After they add you, accept the invite here." /></Card></div>
  const stats = [['TODAY', d?.today], ['UPCOMING', d?.upcoming], ['COMPLETED', d?.completed], ['AI-BOOKED TODAY', d?.ai_today], ['QUESTIONNAIRES DUE', d?.questionnaires_due]]
  return <div><PageHead title="Doctor dashboard" sub="Your day, availability and pre-visit readiness — including AI-booked visits." />
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {stats.map(([l, v]) => <Card key={l}><div className="text-xs font-bold text-ink-soft">{l}</div><div className="text-3xl font-bold">{v ?? '–'}</div></Card>)}
    </div>
    <Card className="mt-4"><div className="font-bold mb-2">Schedule</div>{today.length ? today.map(a => <Link key={a.id} to={`/doctor/appointments/${a.id}`} className="flex flex-wrap items-center justify-between gap-2 text-sm py-2 border-t border-slate-100"><span>{new Date(a.starts_at).toLocaleString()} · {a.patient_name}</span><span className="flex gap-1.5"><AiBadge a={a} /><Pill value={a.status} /></span></Link>) : <Empty title="No appointments" />}</Card>
    <div className="mt-4 flex flex-wrap gap-2 text-sm"><Link to="/doctor/availability" className="btn-ghost">Manage availability</Link><Link to="/doctor/calendar" className="btn-ghost">2-week calendar</Link></div></div>
}
export function ApptList({ title, filter }) {
  const [rows, setRows] = useState([]); const [f, setF] = useState('all')
  useEffect(() => { api('/appointments').then(setRows).catch(() => {}) }, [])
  const statuses = ['all', 'confirmed', 'pending', 'rescheduled', 'completed', 'cancelled', 'no_show']
  const list = rows.filter(a => (!filter || filter(a)) && (f === 'all' || a.status === f))
  return <div><PageHead title={title} right={<select className="input !w-auto text-sm" aria-label="Filter by status" value={f} onChange={e => setF(e.target.value)}>{statuses.map(s => <option key={s} value={s}>{s === 'all' ? 'All statuses' : s}</option>)}</select>} />
    <Card>{list.length ? list.map(a => <Link key={a.id} to={`/doctor/appointments/${a.id}`} className="flex flex-wrap items-center justify-between gap-2 text-sm py-2.5 border-t border-slate-100"><span><b>{new Date(a.starts_at).toLocaleString()}</b> · {a.patient_name} <span className="text-ink-soft">· {a.reason?.slice(0, 40)}</span></span><span className="flex gap-1.5"><AiBadge a={a} /><Pill value={a.status} /></span></Link>) : <Empty title="Nothing here" />}</Card></div>
}
export function Calendar() {
  const [rows, setRows] = useState([])
  useEffect(() => { api('/appointments').then(setRows).catch(() => {}) }, [])
  const days = [...Array(14)].map((_, i) => { const d = new Date(); d.setDate(d.getDate() + i); return d })
  return <div><PageHead title="Calendar" sub="2-week availability overlay." />
    <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">{days.map(d => { const k = d.toDateString(); const items = rows.filter(a => new Date(a.starts_at).toDateString() === k)
      return <Card key={k} className="!p-3 min-h-[110px]"><div className="text-xs font-bold">{d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })}</div>{items.map(a => <Link key={a.id} to={`/doctor/appointments/${a.id}`} className="block text-[11px] mt-1 bg-teal-soft rounded-lg px-1.5 py-1">{new Date(a.starts_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} {a.patient_name?.split(' ')[0]}</Link>)}</Card> })}</div></div>
}
export function Availability() {
  const [cals, setCals] = useState([]); const [blocks, setBlocks] = useState([]); const [sel, setSel] = useState(null)
  const [nb, setNb] = useState({ starts_at: '', ends_at: '', reason: '' }); const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false)
  const load = async () => { const me = await api('/auth/me'); const cs = await api(`/calendars?doctor_id=${me.doctor_id}`); setCals(cs); if (cs[0]) { setSel(cs[0].id); setBlocks(await api(`/blocked-slots?calendar_id=${cs[0].id}`)) } }
  useEffect(() => { load().catch(() => setMsg('Could not load calendars.')) }, [])
  const addBlock = async () => {
    setMsg('')
    if (!sel || !nb.starts_at || !nb.ends_at) { setMsg('Start, end and calendar are required.'); return }
    setBusy(true)
    try { await api('/blocked-slots', { method: 'POST', body: { calendar_id: sel, starts_at: new Date(nb.starts_at).toISOString(), ends_at: new Date(nb.ends_at).toISOString(), reason: nb.reason || 'blocked' } }); setNb({ starts_at: '', ends_at: '', reason: '' }); load() }
    catch (e) { setMsg(`Could not block: ${e.message}`) } finally { setBusy(false) }
  }
  const removeBlock = async (b) => {
    if (!window.confirm(`Unblock ${new Date(b.starts_at).toLocaleString()}? Patients will be able to book it again.`)) return
    try { await api(`/blocked-slots/${b.id}`, { method: 'DELETE' }); load() } catch (e) { setMsg(`Could not remove: ${e.message}`) }
  }
  return <div><PageHead title="Availability & blocked time" sub="Working hours from your calendar; blocks and leave win over everything." />
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    <div className="grid md:grid-cols-2 gap-4">
      <Card><div className="font-bold mb-2">Calendars</div>{cals.map(c => <div key={c.id} className="text-sm py-2 border-t border-slate-100"><b>{c.name}</b> · {c.is_active ? 'active' : 'paused'}<div className="text-xs text-ink-soft font-mono">{c.working_hours}</div></div>)}{!cals.length && <div className="text-sm text-ink-soft">No calendars yet — ask your hospital admin to provision one.</div>}</Card>
      <Card><div className="font-bold mb-2">Blocked slots</div>
        {blocks.map(b => <div key={b.id} className="flex justify-between gap-2 text-sm py-1.5 border-t border-slate-100"><span>{new Date(b.starts_at).toLocaleString()} — {b.reason}</span><button type="button" className="text-crit text-xs font-bold shrink-0" onClick={() => removeBlock(b)}>Remove</button></div>)}
        {!blocks.length && <div className="text-sm text-ink-soft">No blocked time.</div>}
        <div className="mt-3 space-y-2">
          <div><label htmlFor="blk-start" className="text-xs font-bold">START</label><input id="blk-start" className="input mt-1" type="datetime-local" value={nb.starts_at} onChange={e => setNb({ ...nb, starts_at: e.target.value })} /></div>
          <div><label htmlFor="blk-end" className="text-xs font-bold">END</label><input id="blk-end" className="input mt-1" type="datetime-local" value={nb.ends_at} onChange={e => setNb({ ...nb, ends_at: e.target.value })} /></div>
          <div><label htmlFor="blk-reason" className="text-xs font-bold">REASON</label><input id="blk-reason" className="input mt-1" placeholder="e.g. Surgery, leave" value={nb.reason} onChange={e => setNb({ ...nb, reason: e.target.value })} /></div>
        <button type="button" className="btn-primary text-sm" disabled={busy} onClick={addBlock}>{busy ? 'Blocking…' : 'Block time'}</button></div></Card>
    </div></div>
}
export function ApptDetail() {
  const { id } = useParams()
  const [a, setA] = useState(null); const [qs, setQs] = useState([]); const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false)
  const load = () => api(`/appointments/${id}`).then(setA).catch(() => setMsg('Could not load this visit.'))
  useEffect(() => { load(); api(`/questionnaire-responses?appointment_id=${id}`).then(setQs).catch(() => {}) }, [id])
  const finish = async (to) => {
    setMsg(''); setBusy(true)
    try { const r = await api(`/appointments/${id}/complete`, { method: 'POST', body: { to } }); setMsg(to === 'completed' ? 'Visit marked completed.' : 'Marked as no-show.'); load() }
    catch (e) { setMsg(`Could not update: ${e.message}`) } finally { setBusy(false) }
  }
  if (!a) return <div className="p-8">{msg || 'Loading…'}</div>
  const actionable = ['confirmed', 'rescheduled', 'pending'].includes(a.status)
  return <div><PageHead title={`Visit #${a.id} — ${a.patient_name}`} right={actionable ? <><button type="button" disabled={busy} onClick={() => finish('completed')} className="btn-primary text-sm">Complete visit</button><button type="button" disabled={busy} onClick={() => finish('no_show')} className="btn-ghost text-sm">No-show</button></> : null} />
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    <div className="grid md:grid-cols-2 gap-4">
      <Card><div className="flex flex-wrap gap-1.5"><Pill value={a.status} /><AiBadge a={a} /><Pill value={a.integration_status} /></div>
        <div className="mt-3 text-sm space-y-1.5"><div><b>When:</b> {new Date(a.starts_at).toLocaleString()} → {new Date(a.ends_at).toLocaleTimeString()}</div><div><b>Mode:</b> {a.mode || 'in_person'}</div><div><b>Patient-reported reason:</b> {a.reason || '—'}</div><div><b>External ID:</b> <code>{a.external_id || '—'}</code></div><div><b>Correlation:</b> <code>{a.correlation_id}</code></div>
        {a.via_ai && <div className="rounded-xl bg-violet-50 p-2.5 text-violet-900">Booked through the AI assistant{a.conversation_id ? ` (conversation #${a.conversation_id})` : ''} — the reason above was collected conversationally.</div>}
        <div className="text-ink-soft">Only authorized pre-visit info is shown.</div></div></Card>
      <Card><div className="font-bold mb-2">Questionnaire responses</div>{qs.length ? qs.map(r => <div key={r.id} className="text-sm border-t border-slate-100 py-2"><div className="flex gap-1.5"><Pill value={r.status} /><span className="text-ink-soft text-xs">{r.questionnaire_title || ''} · via {r.collected_via || 'web'}</span></div><pre className="mt-1 text-xs bg-slate-50 rounded-xl p-2 overflow-auto">{JSON.stringify(r.answers, null, 1)}</pre></div>) : <div className="text-sm text-ink-soft">No responses yet.</div>}</Card>
    </div></div>
}
