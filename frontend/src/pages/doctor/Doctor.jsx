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
  const [d, setD] = useState(null); const [today, setToday] = useState([]); const [prof, setProf] = useState(null); const [acts, setActs] = useState([])
  useEffect(() => { api('/dashboard/doctor').then(setD).catch(() => {}); api('/appointments').then(r => setToday(r.slice(0, 8))).catch(() => {}); api('/auth/me').then(me => { if (me.doctor_id) api(`/doctors/${me.doctor_id}`).then(setProf).catch(() => {}) }).catch(() => {}); api('/activity').then(r => setActs(r.slice(0, 5))).catch(() => {}) }, [])
  if (user && !user.doctor_id) return <div><PageHead title="Doctor dashboard" sub="Your hospital invite is pending." /><Card><Empty title="Awaiting hospital" sub="Share your login email with your hospital admin. After they add you, accept the invite here." /></Card></div>
  const stats = [['TODAY', d?.today], ['UPCOMING', d?.upcoming], ['COMPLETED', d?.completed], ['AI-BOOKED TODAY', d?.ai_today], ['QUESTIONNAIRES DUE', d?.questionnaires_due]]
  return <div><PageHead title="Doctor dashboard" sub="Your day, availability and pre-visit readiness — including AI-booked visits." />
    {prof && <Card className="mb-4 flex items-center gap-4"><Avatar name={prof.name} size={52} photo={prof.photo_url} seed={prof.id} plain={false} /><div className="text-sm"><div className="font-bold">{prof.name} · {prof.specialty}</div><div className="text-ink-soft">{prof.hospital_name}{prof.hospital_city ? ` (${prof.hospital_city})` : ''} · ★ {prof.avg_rating ?? prof.rating} ({prof.review_count ?? 0}) · {prof.completed_visits ?? 0} completed</div></div><Link to="/doctor/profile" className="btn-ghost text-xs ml-auto shrink-0">My profile</Link></Card>}
    <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
      {stats.map(([l, v]) => <Card key={l}><div className="text-xs font-bold text-ink-soft">{l}</div><div className="text-3xl font-bold">{v ?? '–'}</div></Card>)}
    </div>
    <Card className="mt-4"><div className="font-bold mb-2">Schedule</div>{today.length ? today.map(a => <Link key={a.id} to={`/doctor/appointments/${a.id}`} className="flex flex-wrap items-center justify-between gap-2 text-sm py-2 border-t border-slate-100"><span>{new Date(a.starts_at).toLocaleString()} · {a.patient_name}</span><span className="flex gap-1.5"><AiBadge a={a} /><Pill value={a.status} /></span></Link>) : <Empty title="No appointments" />}</Card>
    {!!acts.length && <Card className="mt-4"><div className="font-bold mb-2">Recent activity</div>{acts.map((a, i) => <div key={i} className="text-sm py-1.5 border-t border-slate-100"><span className="font-mono text-xs text-ink-soft">{a.at?.slice(0, 16)}</span> · <b>{a.kind}</b> · {a.text}</div>)}<Link to="/doctor/activity" className="btn-ghost text-xs mt-2 inline-block">View all activity →</Link></Card>}
    <div className="mt-4 flex flex-wrap gap-2 text-sm"><Link to="/doctor/availability" className="btn-ghost">Manage availability</Link><Link to="/doctor/calendar" className="btn-ghost">2-week calendar</Link></div></div>
}
export function ApptList({ title, filter }) {
  const [rows, setRows] = useState([]); const [f, setF] = useState('all'); const [qmap, setQmap] = useState({})
  useEffect(() => { api('/appointments').then(setRows).catch(() => {}); api('/questionnaire-responses').then(rs => { const m = {}; rs.forEach(r => { if (r.appointment_id) m[r.appointment_id] = r.status }); setQmap(m) }).catch(() => {}) }, [])
  const statuses = ['all', 'confirmed', 'pending', 'rescheduled', 'completed', 'cancelled', 'no_show']
  const list = rows.filter(a => (!filter || filter(a)) && (f === 'all' || a.status === f))
  const qp = (a) => qmap[a.id] === 'completed' ? <span className="pill bg-emerald-50 text-emerald-700">Q done</span> : qmap[a.id] ? <span className="pill bg-amber-50 text-amber-700">Q {qmap[a.id]}</span> : null
  return <div><PageHead title={title} right={<select className="input !w-auto text-sm" aria-label="Filter by status" value={f} onChange={e => setF(e.target.value)}>{statuses.map(s => <option key={s} value={s}>{s === 'all' ? 'All statuses' : s}</option>)}</select>} />
    <Card>{list.length ? list.map(a => <Link key={a.id} to={`/doctor/appointments/${a.id}`} className="flex flex-wrap items-center justify-between gap-2 text-sm py-2.5 border-t border-slate-100"><span><b>{new Date(a.starts_at).toLocaleString()}</b> · {a.patient_name} <span className="text-ink-soft">· {a.reason?.slice(0, 40)}</span></span><span className="flex gap-1.5"><AiBadge a={a} />{qp(a)}<Pill value={a.status} /></span></Link>) : <Empty title="Nothing here" />}</Card></div>
}
export function Questionnaires() {
  const [rows, setRows] = useState([]); const [appts, setAppts] = useState([]); const [msg, setMsg] = useState('')
  useEffect(() => {
    api('/questionnaire-responses').then(setRows).catch(() => setMsg('Could not load questionnaires.'))
    api('/appointments').then(setAppts).catch(() => {})
  }, [])
  const byAppt = {}; rows.forEach(r => { if (r.appointment_id) (byAppt[r.appointment_id] = byAppt[r.appointment_id] || []).push(r) })
  const now = new Date()
  const upcoming = appts.filter(a => new Date(a.starts_at) >= now && ['confirmed', 'pending', 'rescheduled'].includes(a.status)).sort((x, y) => new Date(x.starts_at) - new Date(y.starts_at))
  const done = rows.filter(r => r.status === 'completed').sort((x, y) => y.id - x.id)
  return <div><PageHead title="Questionnaires" sub="Pre-visit information for your appointments only — admin info, never clinical decisions." />
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    <Card className="mb-4"><div className="font-bold mb-2">Upcoming slots needing answers ({upcoming.filter(a => !(byAppt[a.id] || []).some(r => r.status === 'completed')).length})</div>{upcoming.length ? upcoming.map(a => { const rs = byAppt[a.id] || []; const ok = rs.some(r => r.status === 'completed'); return <Link key={a.id} to={`/doctor/appointments/${a.id}`} className="flex flex-wrap justify-between gap-2 text-sm py-2 border-t border-slate-100"><span><b>{new Date(a.starts_at).toLocaleString()}</b> · {a.patient_name}</span><span>{ok ? <span className="pill bg-emerald-50 text-emerald-700">Q done</span> : rs.length ? <span className="pill bg-amber-50 text-amber-700">Q {rs[0].status}</span> : <span className="pill bg-slate-100 text-slate-500">Q —</span>}</span></Link> }) : <Empty title="No upcoming appointments" />}</Card>
    <Card><div className="font-bold mb-2">Completed responses</div>{done.length ? done.map(r => <Link key={r.id} to={r.appointment_id ? `/doctor/appointments/${r.appointment_id}` : '#'} className="block text-sm py-2 border-t border-slate-100"><div className="flex gap-1.5 items-center"><Pill value={r.status} /><span className="text-ink-soft text-xs">{r.questionnaire_title || ''} · via {r.collected_via || 'web'}</span></div><pre className="mt-1 text-xs bg-slate-50 rounded-xl p-2 overflow-auto">{JSON.stringify(r.answers, null, 1).slice(0, 400)}</pre></Link>) : <div className="text-sm text-ink-soft">No completed responses yet.</div>}</Card></div>
}
export function Calendar() {
  const [rows, setRows] = useState([]); const [off, setOff] = useState([]); const [qmap, setQmap] = useState({})
  useEffect(() => {
    api('/appointments').then(setRows).catch(() => {})
    api('/questionnaire-responses').then(rs => { const m = {}; rs.forEach(r => { if (r.appointment_id) m[r.appointment_id] = r.status }); setQmap(m) }).catch(() => {})
    api('/auth/me').then(me => {
      if (!me.doctor_id) return
      api(`/calendars?doctor_id=${me.doctor_id}`).then(async cs => {
        const items = []
        for (const c of cs) {
          const bs = await api(`/blocked-slots?calendar_id=${c.id}`).catch(() => [])
          bs.forEach(b => items.push({ ...b, kind: 'blocked' }))
        }
        const lv = await api(`/leaves?doctor_id=${me.doctor_id}`).catch(() => [])
        lv.forEach(l => items.push({ starts_at: l.starts_at, ends_at: l.ends_at, reason: l.reason, kind: 'leave' }))
        setOff(items)
      }).catch(() => {})
    }).catch(() => {})
  }, [])
  const days = [...Array(14)].map((_, i) => { const d = new Date(); d.setDate(d.getDate() + i); return d })
  return <div><PageHead title="Calendar" sub="Schedule plus blocked and leave time (read-only — managed with your admin)." />
    <div className="grid grid-cols-2 sm:grid-cols-4 md:grid-cols-7 gap-2">{days.map(d => { const k = d.toDateString(); const items = rows.filter(a => new Date(a.starts_at).toDateString() === k); const outs = off.filter(o => new Date(o.starts_at).toDateString() === k)
      return <Card key={k} className="!p-3 min-h-[110px]"><div className="text-xs font-bold">{d.toLocaleDateString([], { weekday: 'short', month: 'short', day: 'numeric' })}</div>{items.map(a => <Link key={a.id} to={`/doctor/appointments/${a.id}`} className="block text-[11px] mt-1 bg-teal-soft rounded-lg px-1.5 py-1">{new Date(a.starts_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} {a.patient_name?.split(' ')[0]}{qmap[a.id] === 'completed' ? ' 🟢' : qmap[a.id] ? ' 🟡' : ''}</Link>)}{outs.map((o, i) => <div key={i} className="block text-[11px] mt-1 bg-slate-100 text-slate-500 rounded-lg px-1.5 py-1">{o.kind === 'leave' ? '🌴 leave' : '⛔ blocked'}{o.reason ? ` · ${o.reason.slice(0, 18)}` : ''}</div>)}</Card> })}</div></div>
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
export function Profile() {
  const [d, setD] = useState(null); const [rev, setRev] = useState(null); const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false)
  const [f, setF] = useState({ qualifications: '', experience_years: 0, duration_minutes: 30, languages: 'English' })
  const load = async () => {
    try {
      const me = await api('/auth/me')
      if (!me.doctor_id) { setMsg('Awaiting hospital — share your login email with your hospital admin.'); return }
      const r = await api(`/doctors/${me.doctor_id}`)
      setD(r); setF({ qualifications: r.qualifications || '', experience_years: r.experience_years || 0, duration_minutes: r.duration_minutes || 30, languages: Array.isArray(r.languages) ? r.languages.join(', ') : (r.languages || 'English') })
      api(`/reviews/summary?doctor_id=${r.id}`).then(setRev).catch(() => {})
    } catch (e) { setMsg('Could not load profile.') }
  }
  useEffect(() => { load() }, [])
  const save = async () => {
    setBusy(true); setMsg('')
    try {
      const me = await api('/auth/me')
      await api(`/doctors/${me.doctor_id}`, { method: 'PATCH', body: { qualifications: f.qualifications, experience_years: Number(f.experience_years) || 0, duration_minutes: Number(f.duration_minutes) || 30, languages: String(f.languages).split(',').map(s => s.trim()).filter(Boolean) } })
      setMsg('Profile saved.'); load()
    } catch (e) { setMsg(`Could not save: ${e.message}`) } finally { setBusy(false) }
  }
  if (!d) return <div className="p-8">{msg || 'Loading…'}</div>
  return <div><PageHead title="My profile" sub="You manage the editable fields — hospital-controlled rows stay locked." right={<Pill value={d.status} />} />
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    <div className="grid md:grid-cols-2 gap-4">
      <Card><div className="flex items-center gap-4 mb-3"><Avatar name={d.name} size={64} photo={d.photo_url} seed={d.id} plain={false} /><div><div className="font-bold text-lg">{d.name}</div><div className="text-sm text-ink-soft">{d.specialty} · {d.hospital_name}{d.hospital_city ? ` (${d.hospital_city})` : ''}</div><div className="text-sm mt-1">★ {rev?.avg ?? d.rating} ({rev?.count ?? d.review_count ?? 0} reviews)</div></div></div>
        <div className="text-sm space-y-1.5"><div><b>Department:</b> managed by hospital admin 🔒</div><div><b>Specialty:</b> {d.specialty} 🔒</div><div><b>Hospital:</b> {d.hospital_name} 🔒</div><div><b>External provider ID:</b> <code>{d.external_provider_id}</code> 🔒</div><div><b>Completed visits:</b> {d.completed_visits ?? 0}</div></div></Card>
      <Card><div className="font-bold mb-2">Editable information</div><div className="grid gap-2 text-sm">
        <div><label className="text-xs font-bold">QUALIFICATIONS</label><input className="input mt-1" value={f.qualifications} onChange={e => setF({ ...f, qualifications: e.target.value })} /></div>
        <div className="grid grid-cols-2 gap-2"><div><label className="text-xs font-bold">EXPERIENCE (YRS)</label><input className="input mt-1" type="number" value={f.experience_years} onChange={e => setF({ ...f, experience_years: e.target.value })} /></div><div><label className="text-xs font-bold">DURATION (MIN)</label><input className="input mt-1" type="number" value={f.duration_minutes} onChange={e => setF({ ...f, duration_minutes: e.target.value })} /></div></div>
        <div><label className="text-xs font-bold">LANGUAGES (comma separated)</label><input className="input mt-1" value={f.languages} onChange={e => setF({ ...f, languages: e.target.value })} /></div>
        <div><label className="text-xs font-bold">CONSULTATION TYPES (view — managed by hospital)</label><div className="text-ink-soft">{d.consultation_types}</div></div>
        <div><button type="button" disabled={busy} onClick={save} className="btn-primary text-sm">Save</button></div>
      </div></Card>
    </div></div>
}
export function Activity() {
  const [rows, setRows] = useState([]); const [msg, setMsg] = useState('')
  useEffect(() => { api('/activity').then(setRows).catch(() => setMsg('Could not load activity.')) }, [])
  return <div><PageHead title="My activity" sub="Profile, availability, schedule and appointment events touching you." />
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    <Card>{rows.map((a, i) => <div key={i} className="text-sm py-1.5 border-t border-slate-100"><span className="font-mono text-xs text-ink-soft">{a.at?.slice(0, 19)}</span> · <b>{a.kind}</b> · {a.text} <code className="text-xs text-ink-faint">{a.corr}</code></div>)}{!rows.length && !msg && <Empty title="No activity yet" sub="Your profile and schedule changes will appear here." />}</Card></div>
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
