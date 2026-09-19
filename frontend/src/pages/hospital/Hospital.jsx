import React, { useEffect, useState } from 'react'
import { Link, useParams, useNavigate } from 'react-router-dom'
import { api } from '../../api/client.js'
import { Card, PageHead, Pill, Avatar, Empty } from '../../components/ui.jsx'
import { BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, PieChart, Pie, Cell } from 'recharts'

function useHid() { const [me, setMe] = useState(null); useEffect(() => { api('/auth/me').then(setMe).catch(() => {}) }, []); return me?.hospital_id }

const DAYS = [['mon', 'Monday'], ['tue', 'Tuesday'], ['wed', 'Wednesday'], ['thu', 'Thursday'], ['fri', 'Friday'], ['sat', 'Saturday'], ['sun', 'Sunday']]

export function Profile() {
  const hid = useHid(); const [tab, setTab] = useState('profile')
  const [h, setH] = useState(null); const [depts, setDepts] = useState([]); const [specs, setSpecs] = useState([])
  const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false)
  const [f, setF] = useState({ name: '', address: '', city: '', phone: '', contact_email: '' })
  const [newDept, setNewDept] = useState(''); const [newSpec, setNewSpec] = useState('')
  const [services, setServices] = useState([]); const [svcIn, setSvcIn] = useState('')
  const [hours, setHours] = useState({})
  const load = () => {
    if (!hid) return
    api(`/hospitals/${hid}`).then(r => { setH(r); setF({ name: r.name || '', address: r.address || '', city: r.city || '', phone: r.phone || '', contact_email: r.contact_email || '' }); try { setServices(JSON.parse(r.services || '[]')) } catch { setServices([]) }; try { setHours(JSON.parse(r.operating_hours || '{}')) } catch { setHours({}) } }).catch(() => setMsg('Could not load hospital profile.'))
    api(`/hospitals/${hid}/departments`).then(setDepts).catch(() => {})
    api(`/hospitals/${hid}/specialties`).then(setSpecs).catch(() => {})
  }
  useEffect(load, [hid])
  const save = async (body, okMsg) => {
    setBusy(true); setMsg('')
    try { await api(`/hospitals/${hid}`, { method: 'PATCH', body }); setMsg(okMsg); load() }
    catch (e) { setMsg(`Could not save: ${e.message}`) } finally { setBusy(false) }
  }
  const TABS = [['profile', 'Profile'], ['departments', 'Departments'], ['specialties', 'Specialties'], ['services', 'Services'], ['hours', 'Hours']]
  return <div><PageHead title="Hospital" sub="Profile, departments, specialties, services and hours — photo stays automatic." />
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    <div className="flex flex-wrap gap-2 mb-4">{TABS.map(([k, l]) => <button key={k} type="button" onClick={() => setTab(k)} className={tab === k ? 'btn-primary text-sm' : 'btn-ghost text-sm'}>{l}</button>)}</div>
    {tab === 'profile' && <Card><div className="grid md:grid-cols-2 gap-3">{[['name', 'Hospital name'], ['city', 'City'], ['address', 'Address'], ['phone', 'Phone'], ['contact_email', 'Contact email']].map(([k, l]) => <div key={k}><label className="text-xs font-bold">{l.toUpperCase()}</label><input className="input mt-1" value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })} /></div>)}</div><button type="button" disabled={busy} onClick={() => save(f, 'Profile saved.')} className="btn-primary text-sm mt-3">Save profile</button></Card>}
    {tab === 'departments' && <Card><div className="font-bold mb-2">Departments ({depts.length})</div>{depts.map(d => <DeptRow key={d.id} d={d} hid={hid} reload={load} setMsg={setMsg} />)}<div className="flex gap-2 mt-3"><input className="input" placeholder="New department, e.g. Cardiology" value={newDept} onChange={e => setNewDept(e.target.value)} /><button type="button" className="btn-primary text-sm shrink-0" onClick={async () => { if (!newDept.trim()) return; try { await api(`/hospitals/${hid}/departments`, { method: 'POST', body: { name: newDept.trim() } }); setNewDept(''); setMsg('Department added.'); load() } catch (e) { setMsg(`Could not add: ${e.message}`) } }}>Add</button></div></Card>}
    {tab === 'specialties' && <Card><div className="font-bold mb-2">Specialties ({specs.length})</div>{specs.filter(s => s.hospital_id).map(s => <SpecRow key={s.id} s={s} hid={hid} reload={load} setMsg={setMsg} />)}{!specs.filter(s => s.hospital_id).length && <div className="text-sm text-ink-soft">No hospital specialties yet — global ones still apply.</div>}<div className="flex gap-2 mt-3"><input className="input" placeholder="New specialty, e.g. Oncology" value={newSpec} onChange={e => setNewSpec(e.target.value)} /><button type="button" className="btn-primary text-sm shrink-0" onClick={async () => { if (!newSpec.trim()) return; try { await api(`/hospitals/${hid}/specialties`, { method: 'POST', body: { name: newSpec.trim() } }); setNewSpec(''); setMsg('Specialty added.'); load() } catch (e) { setMsg(`Could not add: ${e.message}`) } }}>Add</button></div></Card>}
    {tab === 'services' && <Card><div className="font-bold mb-2">Services</div><div className="flex flex-wrap gap-2 mb-3">{services.map(s => <span key={s} className="pill bg-brand-soft text-brand-ink">{s} <button type="button" aria-label={`Remove ${s}`} className="ml-1 font-bold" onClick={() => setServices(services.filter(x => x !== s))}>×</button></span>)}{!services.length && <span className="text-sm text-ink-soft">No services listed.</span>}</div><div className="flex gap-2"><input className="input" placeholder="Add service, e.g. pharmacy" value={svcIn} onChange={e => setSvcIn(e.target.value)} /><button type="button" className="btn-ghost text-sm shrink-0" onClick={() => { if (svcIn.trim() && !services.includes(svcIn.trim())) setServices([...services, svcIn.trim()]); setSvcIn('') }}>Add</button><button type="button" disabled={busy} onClick={() => save({ services }, 'Services saved.')} className="btn-primary text-sm shrink-0">Save</button></div></Card>}
    {tab === 'hours' && <Card><div className="font-bold mb-2">Operating hours</div>{DAYS.map(([k, l]) => { const win = (hours[k] || [])[0] || []; return <div key={k} className="flex items-center gap-2 text-sm py-1.5 border-t border-slate-100"><span className="w-24 font-semibold">{l}</span><input aria-label={`${l} opens`} className="input !w-28" type="time" value={win[0] || ''} onChange={e => setHours({ ...hours, [k]: e.target.value ? [[e.target.value, win[1] || '17:00']] : [] })} /><span>–</span><input aria-label={`${l} closes`} className="input !w-28" type="time" value={win[1] || ''} onChange={e => setHours({ ...hours, [k]: [[win[0] || '09:00', e.target.value]] })} /><button type="button" className="btn-ghost text-xs" onClick={() => setHours({ ...hours, [k]: [] })}>Closed</button></div> })}<button type="button" disabled={busy} onClick={() => save({ operating_hours: hours }, 'Hours saved.')} className="btn-primary text-sm mt-3">Save hours</button></Card>}
  </div>
}

function DeptRow({ d, hid, reload, setMsg }) {
  const [name, setName] = useState(d.name)
  return <div className="flex gap-2 items-center py-1.5 border-t border-slate-100"><input aria-label="Department name" className="input" value={name} onChange={e => setName(e.target.value)} /><button type="button" className="btn-ghost text-xs shrink-0" onClick={async () => { try { await api(`/hospitals/${hid}/departments/${d.id}`, { method: 'PATCH', body: { name } }); setMsg('Department saved.'); reload() } catch (e) { setMsg(`Could not save: ${e.message}`) } }}>Save</button><button type="button" className="text-crit text-xs font-bold shrink-0" onClick={async () => { if (!window.confirm(`Delete ${d.name}? Blocked while doctors are assigned.`)) return; try { await api(`/hospitals/${hid}/departments/${d.id}`, { method: 'DELETE' }); setMsg('Department deleted.'); reload() } catch (e) { setMsg(`Could not delete: ${e.message}`) } }}>Delete</button></div>
}

function SpecRow({ s, hid, reload, setMsg }) {
  const [name, setName] = useState(s.name)
  return <div className="flex gap-2 items-center py-1.5 border-t border-slate-100"><input aria-label="Specialty name" className="input" value={name} onChange={e => setName(e.target.value)} /><button type="button" className="btn-ghost text-xs shrink-0" onClick={async () => { try { await api(`/hospitals/${hid}/specialties/${s.id}`, { method: 'PATCH', body: { name } }); setMsg('Specialty saved.'); reload() } catch (e) { setMsg(`Could not save: ${e.message}`) } }}>Save</button><button type="button" className="text-crit text-xs font-bold shrink-0" onClick={async () => { if (!window.confirm(`Delete ${s.name}? Blocked while doctors are assigned.`)) return; try { await api(`/hospitals/${hid}/specialties/${s.id}`, { method: 'DELETE' }); setMsg('Specialty deleted.'); reload() } catch (e) { setMsg(`Could not delete: ${e.message}`) } }}>Delete</button></div>
}

export function Dash() {
  const hid = useHid(); const [d, setD] = useState(null); const [ready, setReady] = useState(null)
  useEffect(() => { if (hid) api(`/dashboard/hospital?hospital_id=${hid}`).then(setD).catch(() => {}) }, [hid])
  useEffect(() => {
    if (!hid) return
    Promise.all([
      api(`/hospitals/${hid}`).catch(() => null),
      api(`/hospitals/${hid}/departments`).catch(() => []),
      api(`/hospitals/${hid}/specialties`).then(r => r.filter(s => s.hospital_id)).catch(() => []),
      api(`/doctors?hospital_id=${hid}`).then(r => r.filter(x => x.status === 'active')).catch(() => []),
      api(`/questionnaires?hospital_id=${hid}`).catch(() => []),
      api('/workflows').then(r => r.filter(w => w.is_active)).catch(() => []),
      api('/integrations/connections').then(r => r.filter(c => c.status === 'active')).catch(() => []),
      api(`/reviews/summary?hospital_id=${hid}`).catch(() => null),
    ]).then(([h, depts, specs, docs, qs, wfs, conns, rev]) => {
      setReady([
        ['Profile complete', !!(h?.address && h?.city && h?.phone), h ? `${h.city} · ${h.phone}` : ''],
        ['Departments', depts.length > 0, `${depts.length}`],
        ['Specialties', specs.length > 0, `${specs.length}`],
        ['Active doctors', docs.length > 0, `${docs.length}`],
        ['Questionnaires', qs.length > 0, `${qs.length}`],
        ['Workflows active', wfs.length > 0, `${wfs.length}`],
        ['Integration active', conns.length > 0, conns[0]?.vendor || ''],
        ['Reviews', (rev?.count || 0) > 0, rev?.count ? `★ ${rev.avg} (${rev.count})` : 'none yet'],
      ])
    }).catch(() => {})
  }, [hid])
  const cards = [['Appointments', d?.appointments], ['Confirmed', d?.confirmed], ['Doctors', d?.doctors], ['AI-booked', d?.ai_booked], ['AI conversations', d?.ai_conversations], ['Cancelled', d?.cancelled], ['Open reconciliation', d?.reconciliation_open], ['EHR risk', d?.ehr_ops_failed]]
  if (hid === undefined) return <div className="p-8 text-ink-soft">Loading…</div>
  if (!hid) return <div><PageHead title="Hospital overview" sub="Get your hospital approved to unlock this dashboard." /><Card><Empty title="No hospital yet" sub="Register your hospital for System Admin review first." /><Link to="/hospitals/apply" className="btn-primary text-sm mt-3 inline-block">Register hospital →</Link></Card></div>
  return <div><PageHead title="Hospital overview" sub="Bookings, capacity, questionnaires, AI-driven demand, integration risk." />
    <div className="grid grid-cols-2 md:grid-cols-4 gap-4">{cards.map(([l, v]) => <Card key={l}><div className="text-xs font-bold text-ink-soft">{l.toUpperCase()}</div><div className="text-3xl font-bold">{v ?? '–'}</div></Card>)}</div>
    {ready && <Card className="mt-4"><div className="font-bold mb-2">Ready for next phase {ready.every(([, ok]) => ok) ? '✓' : `(${ready.filter(([, ok]) => ok).length}/${ready.length})`}</div><div className="grid sm:grid-cols-2 md:grid-cols-4 gap-2">{ready.map(([l, ok, extra]) => <div key={l} className="flex items-center gap-2 text-sm"><span>{ok ? '✅' : '⬜'}</span><span><b>{l}</b> <span className="text-ink-soft">· {extra}</span></span></div>)}</div>{!ready.every(([, ok]) => ok) && <div className="text-xs text-ink-soft mt-2">Finish: Hospital profile → Doctors → Schedules → Questionnaires → Workflows → Integration.</div>}</Card>}
    {Number(d?.reconciliation_open) > 0 && <Card className="mt-4 !border-red-200"><b className="text-crit">{d.reconciliation_open} reconciliation(s) need attention.</b> <Link to="/hospital/integrations" className="text-teal font-semibold text-sm ml-2">Open integration log →</Link></Card>}
    <div className="grid md:grid-cols-2 gap-4 mt-4">
      <Card><div className="font-bold mb-2">EHR risk</div><div className="text-sm">Failed/unknown ops: <b>{d?.ehr_ops_failed ?? 0}</b></div><div className="text-sm">Questionnaires pending: <b>{d?.questionnaires_pending ?? 0}</b></div></Card>
      <Card><div className="font-bold mb-2">Shortcuts</div><div className="flex flex-wrap gap-2 text-sm"><Link to="/hospital/doctors" className="btn-ghost">Doctors</Link><Link to="/hospital/appointments" className="btn-ghost">Appointments</Link><Link to="/hospital/questionnaires" className="btn-ghost">Questionnaires</Link><Link to="/hospital/ai" className="btn-ghost">AI activity</Link></div></Card>
    </div></div>
}
export function Doctors() {
  const hid = useHid(); const [rows, setRows] = useState([]); const [f, setF] = useState({ name: '', specialty_id: '', department_id: '', email: '', duration_minutes: 30, modes: ['in_person'] }); const [specs, setSpecs] = useState([]); const [depts, setDepts] = useState([]); const [added, setAdded] = useState(null); const [msg, setMsg] = useState('')
  const load = () => hid && api(`/doctors?hospital_id=${hid}`).then(setRows).catch(() => {})
  useEffect(() => { load(); if (hid) { api(`/hospitals/${hid}/specialties`).then(setSpecs).catch(() => {}); api(`/hospitals/${hid}/departments`).then(setDepts).catch(() => {}) } }, [hid])
  const toggleMode = (m) => setF({ ...f, modes: f.modes.includes(m) ? f.modes.filter(x => x !== m) : [...f.modes, m] })
  const create = async () => {
    setMsg(''); setAdded(null)
    if (!f.name.trim()) { setMsg('Name is required.'); return }
    if (!f.email.trim()) { setMsg('Doctor login email is required — the doctor registers first, then you link their email.'); return }
    if (!f.modes.length) { setMsg('Pick at least one consultation type.'); return }
    try {
      const r = await api('/doctors', { method: 'POST', body: { hospital_id: hid, name: f.name.trim(), specialty_id: f.specialty_id ? Number(f.specialty_id) : null, department_id: f.department_id ? Number(f.department_id) : null, email: f.email.trim(), duration_minutes: Number(f.duration_minutes) || 30, consultation_types: f.modes } })
      setF({ name: '', specialty_id: '', department_id: '', email: '', duration_minutes: 30, modes: ['in_person'] }); load()
      setAdded(r)
    } catch (e) { setMsg(`Could not add: ${e.message}`) }
  }
  return <div><PageHead title="Doctors" sub="Lifecycle: invited → active → inactive/suspended. Only active doctors take future bookings." right={<span className="text-sm text-ink-soft">{rows.length} doctors</span>} />
    {hid === undefined && <div className="text-ink-soft">Loading…</div>}
    {hid === null && <Card><Empty title="No hospital yet" sub="Register your hospital for System Admin review first." /><Link to="/hospitals/apply" className="btn-primary text-sm mt-3 inline-block">Register hospital →</Link></Card>}
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    {added && <Card className="mb-3 !border-emerald-300"><div className="font-bold">Doctor linked as invited</div><div className="text-sm mt-1">Doctor ID: <code>#{added.id}</code> · Login: <code>{added.login_email}</code> · Status: <code>invited</code></div><div className="text-xs text-ink-soft mt-1">They keep their own password. Set them active after they accept (doctor phase) or now from Manage.</div></Card>}
    <div className="grid md:grid-cols-3 gap-4">
      <div className="md:col-span-2 space-y-3">{rows.map(d => <Card key={d.id} className="flex items-center gap-4"><Avatar name={d.name} size={48} photo={d.photo_url} seed={d.id} plain={false} /><div className="flex-1"><div className="font-bold">{d.name} <span className="text-xs text-ink-faint">#{d.id}</span></div><div className="text-sm text-ink-soft">{d.specialty} · {d.experience_years}y · ★ {d.rating}</div></div><Pill value={d.status} /><Link to={`/hospital/doctors/${d.id}`} className="btn-ghost text-xs">Manage</Link></Card>)}</div>
      <Card><div className="font-bold mb-2">Add doctor</div>
        <input className="input mb-2" placeholder="Name" value={f.name} onChange={e => setF({ ...f, name: e.target.value })} />
        <select className="input mb-2" value={f.specialty_id} onChange={e => setF({ ...f, specialty_id: e.target.value })}><option value="">Specialty…</option>{specs.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <select className="input mb-2" value={f.department_id} onChange={e => setF({ ...f, department_id: e.target.value })}><option value="">Department…</option>{depts.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select>
        <input className="input mb-2" placeholder="Doctor login email (must be registered)" value={f.email} onChange={e => setF({ ...f, email: e.target.value })} />
        <input className="input mb-2" type="number" min="5" step="5" aria-label="Consultation duration minutes" value={f.duration_minutes} onChange={e => setF({ ...f, duration_minutes: e.target.value })} />
        <div className="flex gap-2 mb-2 text-sm">{['in_person', 'video', 'phone'].map(m => <label key={m} className="flex items-center gap-1"><input type="checkbox" checked={f.modes.includes(m)} onChange={() => toggleMode(m)} />{m.replace('_', ' ')}</label>)}</div>
        <button className="btn-primary w-full text-sm" onClick={create}>Create + provision calendar</button></Card>
    </div></div>
}
export function DoctorDetail() {
  const { id } = useParams(); const nav = useNavigate()
  const [d, setD] = useState(null); const [specs, setSpecs] = useState([]); const [depts, setDepts] = useState([]); const [msg, setMsg] = useState(''); const [busy, setBusy] = useState(false)
  const [f, setF] = useState({ qualifications: '', experience_years: 0, duration_minutes: 30, specialty_id: '', department_id: '' })
  const load = () => api(`/doctors/${id}`).then(r => { setD(r); setF({ qualifications: r.qualifications || '', experience_years: r.experience_years || 0, duration_minutes: r.duration_minutes || 30, specialty_id: '', department_id: '' }); api(`/hospitals/${r.hospital_id}/specialties`).then(setSpecs).catch(() => {}); api(`/hospitals/${r.hospital_id}/departments`).then(setDepts).catch(() => {}) }).catch(() => setMsg('Could not load doctor.'))
  useEffect(load, [id])
  const save = async () => {
    setBusy(true); setMsg('')
    try {
      const body = { qualifications: f.qualifications, experience_years: Number(f.experience_years) || 0, duration_minutes: Number(f.duration_minutes) || 30 }
      if (f.specialty_id) body.specialty_id = Number(f.specialty_id)
      if (f.department_id) body.department_id = Number(f.department_id)
      await api(`/doctors/${id}`, { method: 'PATCH', body }); setMsg('Doctor saved.'); load()
    } catch (e) { setMsg(`Could not save: ${e.message}`) } finally { setBusy(false) }
  }
  const remove = async () => {
    if (!window.confirm(`Deactivate ${d?.name}? Blocked while upcoming appointments exist.`)) return
    try { await api(`/doctors/${id}`, { method: 'DELETE' }); nav('/hospital/doctors') }
    catch (e) { setMsg(`Could not deactivate: ${e.message}`) }
  }
  if (!d) return <div className="p-8">{msg || 'Loading…'}</div>
  return <div><PageHead title={`${d.name} #${d.id}`} right={<select className="input !w-auto" value={d.status} onChange={async e => { await api(`/doctors/${id}`, { method: 'PATCH', body: { status: e.target.value } }); setD({ ...d, status: e.target.value }) }}>{['invited', 'active', 'inactive', 'suspended'].map(s => <option key={s}>{s}</option>)}</select>} />
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    <div className="flex items-center gap-4 mb-4"><Avatar name={d.name} size={64} photo={d.photo_url} seed={d.id} plain={false} /><div className="text-sm text-ink-soft">Auto Unsplash photo — no upload needed. Login owned by the doctor since signup.</div></div>
    <div className="grid md:grid-cols-2 gap-4"><Card><div className="font-bold mb-2">Details</div><div className="grid gap-2 text-sm">
      <div><label className="text-xs font-bold">QUALIFICATIONS</label><input className="input mt-1" value={f.qualifications} onChange={e => setF({ ...f, qualifications: e.target.value })} /></div>
      <div className="grid grid-cols-2 gap-2"><div><label className="text-xs font-bold">EXPERIENCE (YRS)</label><input className="input mt-1" type="number" value={f.experience_years} onChange={e => setF({ ...f, experience_years: e.target.value })} /></div><div><label className="text-xs font-bold">DURATION (MIN)</label><input className="input mt-1" type="number" value={f.duration_minutes} onChange={e => setF({ ...f, duration_minutes: e.target.value })} /></div></div>
      <div><label className="text-xs font-bold">SPECIALTY (now: {d.specialty || '—'})</label><select className="input mt-1" value={f.specialty_id} onChange={e => setF({ ...f, specialty_id: e.target.value })}><option value="">Keep current</option>{specs.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
      <div><label className="text-xs font-bold">DEPARTMENT</label><select className="input mt-1" value={f.department_id} onChange={e => setF({ ...f, department_id: e.target.value })}><option value="">Keep current</option>{depts.map(s => <option key={s.id} value={s.id}>{s.name}</option>)}</select></div>
      <div className="text-ink-soft">External provider ID: <code>{d.external_provider_id}</code></div>
      <div className="flex gap-2"><button type="button" disabled={busy} onClick={save} className="btn-primary text-sm">Save</button><button type="button" onClick={remove} className="btn-ghost text-sm !text-crit">Deactivate</button></div>
    </div></Card>
    <Card><div className="font-bold mb-2">Calendars</div>{d.calendars?.map(c => <div key={c.id} className="text-sm py-1.5 border-t border-slate-100">{c.name} · {c.is_active ? 'active' : 'paused'}</div>)}</Card></div></div>
}
export function Schedules() {
  const hid = useHid(); const [docs, setDocs] = useState([]); const [did, setDid] = useState(''); const [slots, setSlots] = useState([])
  const [cals, setCals] = useState([]); const [calId, setCalId] = useState(''); const [rules, setRules] = useState([])
  const [leaves, setLeaves] = useState([]); const [atypes, setAtypes] = useState([])
  const [msg, setMsg] = useState(''); const [tab, setTab] = useState('slots')
  const [nr, setNr] = useState({ weekday: 0, start_time: '09:00', end_time: '17:00', slot_minutes: 30 })
  const [nl, setNl] = useState({ starts_at: '', ends_at: '', reason: 'leave' })
  const [na, setNa] = useState({ name: '', duration_minutes: 30 })
  const WD = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
  useEffect(() => { if (hid) { api(`/doctors?hospital_id=${hid}`).then(r => { setDocs(r); if (r[0] && !did) setDid(r[0].id) }).catch(() => {}); api(`/appointment-types?hospital_id=${hid}`).then(setAtypes).catch(() => {}) } }, [hid])
  useEffect(() => {
    if (!did) return
    api(`/availability?doctor_id=${did}&days_ahead=7`).then(r => setSlots(r.slots)).catch(() => {})
    api(`/auth/me`).then(me => api(`/calendars?doctor_id=${did}`).then(cs => { setCals(cs); const first = cs[0]?.id || ''; setCalId(first); if (first) api(`/availability-rules?calendar_id=${first}`).then(setRules).catch(() => {}) }).catch(() => {})).catch(() => {})
    api(`/leaves?doctor_id=${did}`).then(setLeaves).catch(() => {})
  }, [did])
  const reloadRules = () => { if (calId) api(`/availability-rules?calendar_id=${calId}`).then(setRules).catch(() => {}); if (did) api(`/availability?doctor_id=${did}&days_ahead=7`).then(r => setSlots(r.slots)).catch(() => {}) }
  return <div><PageHead title="Calendar & availability" sub="Working hours, rules, blocks, leave and visit types — future bookings read this." />
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    <select className="input max-w-sm mb-3" value={did} onChange={e => setDid(e.target.value)}>{docs.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select>
    <div className="flex flex-wrap gap-2 mb-4">{[['slots', 'Open slots'], ['rules', 'Weekly rules'], ['leave', 'Leave'], ['types', 'Visit types']].map(([k, l]) => <button key={k} type="button" onClick={() => setTab(k)} className={tab === k ? 'btn-primary text-sm' : 'btn-ghost text-sm'}>{l}</button>)}</div>
    {tab === 'slots' && <Card><div className="font-bold mb-2">{slots.length} open slots (7 days)</div>{slots.slice(0, 20).map(s => <div key={`${s.calendar_id}-${s.starts_at}`} className="text-sm py-1.5 border-t border-slate-100">{new Date(s.starts_at).toLocaleString()}</div>)}{!slots.length && <Empty title="Fully booked or blocked" />}</Card>}
    {tab === 'rules' && <Card><div className="font-bold mb-2">Weekly rules {calId ? '' : '(no calendar yet)'}</div>
      <select className="input max-w-sm mb-2" aria-label="Calendar" value={calId} onChange={e => { setCalId(e.target.value); if (e.target.value) api(`/availability-rules?calendar_id=${e.target.value}`).then(setRules).catch(() => {}) }}>{cals.map(c => <option key={c.id} value={c.id}>{c.name} {c.is_active ? '' : '(paused)'}</option>)}</select>
      {rules.map(r => <div key={r.id} className="flex flex-wrap items-center gap-2 text-sm py-1.5 border-t border-slate-100"><span className="font-bold w-12">{WD[r.weekday]}</span><span>{r.start_time}–{r.end_time} · {r.slot_minutes}m</span><span className="text-ink-soft">{r.is_active ? '' : '· paused'}</span><button type="button" className="btn-ghost text-xs" onClick={async () => { await api(`/availability-rules/${r.id}`, { method: 'PATCH', body: { is_active: !r.is_active } }); reloadRules() }}>{r.is_active ? 'Pause' : 'Resume'}</button><button type="button" className="text-crit text-xs font-bold" onClick={async () => { if (!window.confirm('Delete this rule?')) return; await api(`/availability-rules/${r.id}`, { method: 'DELETE' }); reloadRules() }}>Delete</button></div>)}
      {!rules.length && <div className="text-sm text-ink-soft">No rules — slots fall back to calendar hours.</div>}
      <div className="grid grid-cols-2 md:grid-cols-5 gap-2 mt-3"><select aria-label="Weekday" className="input" value={nr.weekday} onChange={e => setNr({ ...nr, weekday: Number(e.target.value) })}>{WD.map((w, i) => <option key={w} value={i}>{w}</option>)}</select><input aria-label="Start" className="input" type="time" value={nr.start_time} onChange={e => setNr({ ...nr, start_time: e.target.value })} /><input aria-label="End" className="input" type="time" value={nr.end_time} onChange={e => setNr({ ...nr, end_time: e.target.value })} /><input aria-label="Minutes" className="input" type="number" min="5" step="5" value={nr.slot_minutes} onChange={e => setNr({ ...nr, slot_minutes: Number(e.target.value) })} /><button type="button" className="btn-primary text-sm" onClick={async () => { try { await api('/availability-rules', { method: 'POST', body: { calendar_id: Number(calId), ...nr } }); setMsg('Rule added.'); reloadRules() } catch (e) { setMsg(`Could not add: ${e.message}`) } }}>Add</button></div></Card>}
    {tab === 'leave' && <Card><div className="font-bold mb-2">Leave / unavailable</div>{leaves.map(l => <div key={l.id} className="flex justify-between text-sm py-1.5 border-t border-slate-100"><span>{new Date(l.starts_at).toLocaleString()} → {new Date(l.ends_at).toLocaleString()} · {l.reason}</span><button type="button" className="text-crit text-xs font-bold" onClick={async () => { await api(`/leaves/${l.id}`, { method: 'DELETE' }); api(`/leaves?doctor_id=${did}`).then(setLeaves).catch(() => {}); reloadRules() }}>Remove</button></div>)}{!leaves.length && <div className="text-sm text-ink-soft">No leave recorded.</div>}<div className="grid md:grid-cols-4 gap-2 mt-3"><input aria-label="Leave start" className="input" type="datetime-local" value={nl.starts_at} onChange={e => setNl({ ...nl, starts_at: e.target.value })} /><input aria-label="Leave end" className="input" type="datetime-local" value={nl.ends_at} onChange={e => setNl({ ...nl, ends_at: e.target.value })} /><input aria-label="Reason" className="input" value={nl.reason} onChange={e => setNl({ ...nl, reason: e.target.value })} /><button type="button" className="btn-primary text-sm" onClick={async () => { try { await api('/leaves', { method: 'POST', body: { doctor_id: Number(did), starts_at: new Date(nl.starts_at).toISOString(), ends_at: new Date(nl.ends_at).toISOString(), reason: nl.reason } }); setNl({ starts_at: '', ends_at: '', reason: 'leave' }); setMsg('Leave added.'); api(`/leaves?doctor_id=${did}`).then(setLeaves).catch(() => {}); reloadRules() } catch (e) { setMsg(`Could not add: ${e.message}`) } }}>Add leave</button></div></Card>}
    {tab === 'types' && <Card><div className="font-bold mb-2">Appointment types</div>{atypes.map(a => <TypeRow key={a.id} a={a} reload={() => hid && api(`/appointment-types?hospital_id=${hid}`).then(setAtypes).catch(() => {})} setMsg={setMsg} />)}<div className="grid md:grid-cols-3 gap-2 mt-3"><input aria-label="Type name" className="input" placeholder="e.g. Video follow-up" value={na.name} onChange={e => setNa({ ...na, name: e.target.value })} /><input aria-label="Minutes" className="input" type="number" min="5" step="5" value={na.duration_minutes} onChange={e => setNa({ ...na, duration_minutes: Number(e.target.value) })} /><button type="button" className="btn-primary text-sm" onClick={async () => { try { await api('/appointment-types', { method: 'POST', body: { hospital_id: hid, name: na.name, duration_minutes: na.duration_minutes } }); setNa({ name: '', duration_minutes: 30 }); setMsg('Type added.'); hid && api(`/appointment-types?hospital_id=${hid}`).then(setAtypes).catch(() => {}) } catch (e) { setMsg(`Could not add: ${e.message}`) } }}>Add type</button></div></Card>}
  </div>
}
function TypeRow({ a, reload, setMsg }) {
  const [mins, setMins] = useState(a.duration_minutes)
  return <div className="flex flex-wrap items-center gap-2 text-sm py-1.5 border-t border-slate-100"><b className="flex-1">{a.name}</b><input aria-label="Minutes" className="input !w-24" type="number" min="5" step="5" value={mins} onChange={e => setMins(e.target.value)} /><button type="button" className="btn-ghost text-xs" onClick={async () => { try { await api(`/appointment-types/${a.id}`, { method: 'PATCH', body: { duration_minutes: Number(mins) } }); setMsg('Type saved.'); reload() } catch (e) { setMsg(`Could not save: ${e.message}`) } }}>Save</button><button type="button" className="text-crit text-xs font-bold" onClick={async () => { if (!window.confirm(`Delete ${a.name}? Blocked while appointments use it.`)) return; try { await api(`/appointment-types/${a.id}`, { method: 'DELETE' }); setMsg('Type deleted.'); reload() } catch (e) { setMsg(`Could not delete: ${e.message}`) } }}>Delete</button></div>
}
export function Appointments() {
  const [rows, setRows] = useState([]); const [f, setF] = useState('all'); const [aiOnly, setAiOnly] = useState(false)
  useEffect(() => { api('/appointments').then(setRows).catch(() => {}) }, [])
  const list = rows.filter(a => (f === 'all' || a.status === f) && (!aiOnly || a.via_ai))
  return <div><PageHead title="Appointments" sub="Every booking with verification state — including AI-driven ones." right={<span className="flex gap-2"><button type="button" onClick={() => setAiOnly(!aiOnly)} className={aiOnly ? 'btn-primary text-xs' : 'btn-ghost text-xs'}>{aiOnly ? '✓ AI-booked only' : 'AI-booked only'}</button><select className="input !w-auto text-sm" aria-label="Filter by status" value={f} onChange={e => setF(e.target.value)}>{['all', 'confirmed', 'pending', 'rescheduled', 'cancelled', 'completed', 'no_show', 'failed', 'reconciliation_required'].map(s => <option key={s} value={s}>{s === 'all' ? 'All statuses' : s}</option>)}</select></span>} />
    <Card>{list.length ? list.map(a => <div key={a.id} className="flex flex-wrap justify-between gap-2 text-sm py-2.5 border-t border-slate-100"><span><b>#{a.id}</b> {new Date(a.starts_at).toLocaleString()} · {a.doctor_name} · {a.patient_name}</span><span className="flex gap-1.5">{a.via_ai && <span className="pill bg-violet-50 text-violet-700">via AI</span>}<Pill value={a.status} /><Pill value={a.integration_status} /></span></div>) : <Empty title="No appointments match" />}</Card></div>
}
const QTYPES = ['yes_no', 'choice', 'multi', 'numeric', 'date', 'short_text', 'long_text', 'structured']

export function Questionnaires() {
  const hid = useHid(); const [rows, setRows] = useState([]); const [docs, setDocs] = useState([]); const [atypes, setAtypes] = useState([])
  const [msg, setMsg] = useState(''); const [editing, setEditing] = useState(null)
  const [f, setF] = useState({ title: '', description: '', category: 'pre_visit', doctor_id: '', appointment_type_id: '', schema: [{ id: 'q1', label: 'Reason for visit', type: 'long_text', required: true }] })
  const load = () => hid && api(`/questionnaires?hospital_id=${hid}`).then(setRows).catch(() => {})
  useEffect(() => { load(); if (hid) { api(`/doctors?hospital_id=${hid}`).then(setDocs).catch(() => {}); api(`/appointment-types?hospital_id=${hid}`).then(setAtypes).catch(() => {}) } }, [hid])
  const startEdit = async (q) => {
    const full = await api(`/questionnaires/${q.id}`).catch(() => q)
    setEditing(q.id); setF({ title: full.title || '', description: full.description || '', category: 'pre_visit', doctor_id: '', appointment_type_id: '', schema: full.schema || [] }); window.scrollTo(0, 0)
  }
  const reset = () => { setEditing(null); setF({ title: '', description: '', category: 'pre_visit', doctor_id: '', appointment_type_id: '', schema: [{ id: 'q1', label: 'Reason for visit', type: 'long_text', required: true }] }) }
  const save = async () => {
    setMsg('')
    if (!f.title.trim()) { setMsg('Title is required.'); return }
    const body = { hospital_id: hid, title: f.title.trim(), description: f.description, category: f.category, doctor_id: f.doctor_id ? Number(f.doctor_id) : null, appointment_type_id: f.appointment_type_id ? Number(f.appointment_type_id) : null, schema: f.schema }
    try {
      if (editing) { await api(`/questionnaires/${editing}`, { method: 'PATCH', body }); setMsg('Questionnaire saved.') }
      else { await api('/questionnaires', { method: 'POST', body }); setMsg('Questionnaire created.') }
      reset(); load()
    } catch (e) { setMsg(`Could not save: ${e.message}`) }
  }
  const updQ = (i, patch) => setF({ ...f, schema: f.schema.map((q, j) => j === i ? { ...q, ...patch } : q) })
  const addQ = () => setF({ ...f, schema: [...f.schema, { id: `q${f.schema.length + 1}`, label: '', type: 'short_text', required: false }] })
  return <div><PageHead title="Questionnaires" sub="Admin-approved pre-visit info only — never diagnosis or prescriptions." />
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    <Card className="mb-4"><div className="font-bold mb-2">{editing ? `Editing #${editing}` : 'Builder'}</div>
      <div className="grid md:grid-cols-2 gap-2 mb-2"><input className="input" placeholder="Title, e.g. Diabetes pre-visit" value={f.title} onChange={e => setF({ ...f, title: e.target.value })} /><input className="input" placeholder="Description" value={f.description} onChange={e => setF({ ...f, description: e.target.value })} /></div>
      <div className="grid md:grid-cols-3 gap-2 mb-2"><select aria-label="Category" className="input" value={f.category} onChange={e => setF({ ...f, category: e.target.value })}>{['pre_visit', 'ortho', 'cardio', 'general'].map(c => <option key={c}>{c}</option>)}</select><select aria-label="Doctor (optional)" className="input" value={f.doctor_id} onChange={e => setF({ ...f, doctor_id: e.target.value })}><option value="">All doctors</option>{docs.map(d => <option key={d.id} value={d.id}>{d.name}</option>)}</select><select aria-label="Visit type (optional)" className="input" value={f.appointment_type_id} onChange={e => setF({ ...f, appointment_type_id: e.target.value })}><option value="">All visit types</option>{atypes.map(a => <option key={a.id} value={a.id}>{a.name}</option>)}</select></div>
      {f.schema.map((q, i) => <div key={i} className="rounded-xl bg-slate-50 p-3 mb-2"><div className="grid md:grid-cols-[1fr_150px_auto] gap-2"><input aria-label="Question label" className="input" placeholder="Question label" value={q.label} onChange={e => updQ(i, { label: e.target.value })} /><select aria-label="Type" className="input" value={q.type} onChange={e => updQ(i, { type: e.target.value })}>{QTYPES.map(t => <option key={t}>{t}</option>)}</select><label className="flex items-center gap-1 text-xs"><input type="checkbox" checked={!!q.required} onChange={e => updQ(i, { required: e.target.checked })} />required</label></div>{(q.type === 'choice' || q.type === 'multi') && <input aria-label="Options comma separated" className="input mt-2" placeholder="Options, comma separated" value={(q.options || []).join(', ')} onChange={e => updQ(i, { options: e.target.value.split(',').map(s => s.trim()).filter(Boolean) })} />}<div className="text-right"><button type="button" className="text-crit text-xs font-bold mt-1" onClick={() => setF({ ...f, schema: f.schema.filter((_, j) => j !== i) })}>Remove</button></div></div>)}
      <div className="flex gap-2"><button type="button" onClick={addQ} className="btn-ghost text-sm">+ Question</button><button type="button" onClick={save} className="btn-primary text-sm">{editing ? 'Save changes' : 'Create'}</button>{editing && <button type="button" onClick={reset} className="btn-ghost text-sm">Cancel</button>}</div>
    </Card>
    {rows.map(q => <QRow key={q.id} q={q} reload={load} setMsg={setMsg} onEdit={() => startEdit(q)} />)}</div>
}
function QRow({ q, reload, setMsg, onEdit }) {
  const [resp, setResp] = useState(null)
  useEffect(() => { api(`/questionnaire-responses?questionnaire_id=${q.id}`).then(r => setResp(r.length)).catch(() => {}) }, [q.id])
  return <Card className="mb-3"><div className="flex flex-wrap items-center gap-2"><div className="font-bold flex-1">{q.title} <span className="text-xs text-ink-faint">· {q.category} · {q.schema?.length || 0} questions · {resp ?? '—'} responses</span></div><Pill value={q.is_active ? 'active' : 'inactive'} /><button type="button" onClick={onEdit} className="btn-ghost text-xs">Edit</button><button type="button" className="btn-ghost text-xs" onClick={async () => { await api(`/questionnaires/${q.id}`, { method: 'PATCH', body: { is_active: !q.is_active } }); setMsg(q.is_active ? 'Deactivated.' : 'Activated.'); reload() }}>{q.is_active ? 'Deactivate' : 'Activate'}</button><button type="button" className="text-crit text-xs font-bold" onClick={async () => { if (!window.confirm(`Delete ${q.title}? Blocked while responses exist.`)) return; try { await api(`/questionnaires/${q.id}`, { method: 'DELETE' }); setMsg('Deleted.'); reload() } catch (e) { setMsg(`Could not delete: ${e.message}`) } }}>Delete</button></div><pre className="text-xs bg-slate-50 rounded-xl p-2 mt-2 overflow-auto">{JSON.stringify(q.schema, null, 1).slice(0, 600)}</pre></Card>
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
  const [ops, setOps] = useState([]); const [conns, setConns] = useState([]); const [recon, setRecon] = useState([]); const [msg, setMsg] = useState(''); const [edit, setEdit] = useState({})
  const load = () => { api('/integrations/operations').then(setOps).catch(() => {}); api('/integrations/connections').then(setConns).catch(() => {}); api('/reconciliation').then(setRecon).catch(() => {}) }
  useEffect(load, [])
  const testConn = async (c) => {
    setMsg('')
    try { const r = await api(`/integrations/connections/${c.id}/test`, { method: 'POST', body: {} }); setMsg(r.ok ? `Connection #${c.id}: reachable.` : `Connection #${c.id}: unreachable — ${r.detail?.slice(0, 120)}`); load() }
    catch (e) { setMsg(`Test failed: ${e.message}`) }
  }
  const saveConn = async (c) => {
    setMsg('')
    try { await api(`/integrations/connections/${c.id}`, { method: 'PATCH', body: { vendor: edit[c.id]?.vendor ?? c.vendor, base_url: edit[c.id]?.base_url ?? c.base_url } }); setMsg('Settings saved. Run Test to verify.'); load() }
    catch (e) { setMsg(`Could not save: ${e.message}`) }
  }
  return <div><PageHead title="Healthcare integration" sub="Simple settings: vendor, address, key status. No appointment operations here." right={<button className="btn-ghost text-sm" onClick={load}>Refresh</button>} />
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    {recon.filter(r => r.status === 'open').map(r => <Card key={r.id} className="mb-3 !border-red-200"><div className="text-sm"><b className="text-crit">Reconciliation #{r.id}</b> · appt #{r.appointment_id} · {r.issue} · <code>{r.correlation_id}</code></div><button className="btn-primary text-xs mt-2" onClick={async () => { await api(`/appointments/${r.appointment_id}/retry-sync`, { method: 'POST', body: {} }); load() }}>Probe EHR + sync now</button></Card>)}
    <div className="grid md:grid-cols-2 gap-4">
      <Card><div className="font-bold mb-2">Connections</div>{conns.map(c => <div key={c.id} className="text-sm py-2 border-t border-slate-100"><div className="flex justify-between items-center"><span>#{c.hospital_id} · {c.vendor} · {c.base_url}</span><Pill value={c.status} /></div><div className="grid grid-cols-2 gap-2 mt-2"><input aria-label="Vendor" className="input" defaultValue={c.vendor} onChange={e => setEdit({ ...edit, [c.id]: { ...edit[c.id], vendor: e.target.value } })} /><input aria-label="Base URL" className="input" defaultValue={c.base_url} onChange={e => setEdit({ ...edit, [c.id]: { ...edit[c.id], base_url: e.target.value } })} /></div><div className="flex gap-2 mt-2"><button type="button" className="btn-ghost text-xs" onClick={() => saveConn(c)}>Save</button><button type="button" className="btn-primary text-xs" onClick={() => testConn(c)}>Test connection</button></div></div>)}{!conns.length && <div className="text-sm text-ink-soft">No connections yet — created on hospital approval.</div>}</Card>
      <Card><div className="font-bold mb-2">Operations</div>{ops.slice(0, 30).map(o => <div key={o.id} className="text-sm py-1.5 border-t border-slate-100"><div className="flex justify-between"><span><code>{o.kind}</code> appt #{o.ref_id}</span><Pill value={o.status} /></div><div className="text-xs text-ink-soft font-mono">{o.correlation_id} · {o.error?.slice(0, 120)}</div></div>)}</Card>
    </div></div>
}
export function Workflows() {
  const [ws, setWs] = useState([]); const [ex, setEx] = useState([]); const [msg, setMsg] = useState('')
  const load = () => { api('/workflows').then(setWs).catch(() => {}); api('/workflow-executions').then(setEx).catch(() => {}) }
  useEffect(load, [])
  const toggle = async (w) => {
    setMsg('')
    try { await api(`/workflows/${w.id}`, { method: 'PATCH', body: { is_active: !w.is_active } }); setMsg(`${w.name} ${w.is_active ? 'paused' : 'resumed'}.`); load() }
    catch (e) { setMsg(`Could not update: ${e.message}`) }
  }
  return <div><PageHead title="Workflows" sub="Fixed catalog for appointments, questionnaires, notifications and recovery. Toggle only — triggers are fixed." />
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    <div className="grid md:grid-cols-2 gap-4">
    <Card><div className="font-bold mb-2">Triggers</div>{ws.map(w => <div key={w.id} className="text-sm py-2 border-t border-slate-100"><div className="flex justify-between items-center gap-2"><b>{w.name}</b><button type="button" onClick={() => toggle(w)} className={w.is_active ? 'btn-ghost text-xs' : 'btn-primary text-xs'}>{w.is_active ? 'Pause' : 'Resume'}</button></div><div className="text-xs text-ink-soft font-mono">on {w.trigger_event} · {w.steps?.length} steps {w.is_active ? '' : '· paused'}</div></div>)}{!ws.length && <div className="text-sm text-ink-soft">No workflows yet.</div>}</Card>
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
export function Reviews() {
  const hid = useHid(); const [rows, setRows] = useState([]); const [summary, setSummary] = useState(null)
  const [f, setF] = useState('all'); const [t, setT] = useState('all'); const [msg, setMsg] = useState(''); const [resp, setResp] = useState({})
  const load = () => { if (!hid) return; api(`/reviews?hospital_id=${hid}`).then(setRows).catch(() => {}); api(`/reviews/summary?hospital_id=${hid}`).then(setSummary).catch(() => {}) }
  useEffect(load, [hid])
  const list = rows.filter(r => (f === 'all' || String(r.rating) === f) && (t === 'all' || r.target_type === t))
  const moderate = async (r, body) => {
    setMsg('')
    try { await api(`/reviews/${r.id}`, { method: 'PATCH', body }); setMsg('Saved.'); load() }
    catch (e) { setMsg(`Could not save: ${e.message}`) }
  }
  return <div><PageHead title="Reviews" sub="Patient ratings after completed visits — this hospital only." />
    {msg && <div className="card p-3 mb-3 text-sm">{msg}</div>}
    <div className="grid md:grid-cols-3 gap-4 mb-4"><Card><div className="text-xs font-bold text-ink-soft">AVERAGE</div><div className="text-3xl font-bold">★ {summary?.avg ?? '–'}</div></Card><Card><div className="text-xs font-bold text-ink-soft">REVIEWS</div><div className="text-3xl font-bold">{summary?.count ?? '–'}</div></Card><Card><div className="text-xs font-bold text-ink-soft">BY STARS</div><div className="text-sm mt-1">{[5, 4, 3, 2, 1].map(s => <div key={s}>★ {s}: <b>{summary?.dist?.[s] || 0}</b></div>)}</div></Card></div>
    <div className="flex flex-wrap gap-2 mb-3"><select aria-label="Filter by stars" className="input !w-auto text-sm" value={f} onChange={e => setF(e.target.value)}>{['all', '5', '4', '3', '2', '1'].map(s => <option key={s} value={s}>{s === 'all' ? 'All stars' : `★ ${s}`}</option>)}</select><select aria-label="Filter by target" className="input !w-auto text-sm" value={t} onChange={e => setT(e.target.value)}>{['all', 'doctor', 'hospital'].map(s => <option key={s} value={s}>{s === 'all' ? 'Doctors + hospital' : s}</option>)}</select></div>
    {list.map(r => <Card key={r.id} className="mb-3"><div className="flex flex-wrap items-center gap-2 text-sm"><b>★ {r.rating}</b><span className="font-bold">{r.title || '(no title)'}</span><span className="text-ink-soft">· {r.target_type} {r.doctor_name || ''} · {r.patient_name} · appt #{r.appointment_id}</span><Pill value={r.status} /></div><div className="text-sm mt-1">{r.body || <span className="text-ink-soft">No comment.</span>}</div>{r.response_text ? <div className="mt-2 rounded-xl bg-slate-50 p-2.5 text-sm"><b>Your response:</b> {r.response_text}</div> : <div className="flex gap-2 mt-2"><input aria-label="Respond" className="input" placeholder="Write a public response…" value={resp[r.id] || ''} onChange={e => setResp({ ...resp, [r.id]: e.target.value })} /><button type="button" className="btn-ghost text-xs shrink-0" onClick={() => moderate(r, { response_text: resp[r.id] || '' })}>Respond</button></div>}<div className="mt-2"><button type="button" className="btn-ghost text-xs" onClick={() => moderate(r, { status: r.status === 'hidden' ? 'approved' : 'hidden' })}>{r.status === 'hidden' ? 'Show' : 'Hide'}</button></div></Card>)}
    {!list.length && <Card><Empty title="No reviews match" sub="Reviews appear after patients rate completed visits." /></Card>}</div>
}
export function Activity() {
  const [rows, setRows] = useState([])
  useEffect(() => { api('/activity').then(setRows).catch(() => {}) }, [])
  return <div><PageHead title="Hospital activity" sub="Doctor, schedule, questionnaire, workflow, integration and review events — this hospital only." />
    <Card>{rows.map((a, i) => <div key={i} className="text-sm py-1.5 border-t border-slate-100"><span className="font-mono text-xs text-ink-soft">{a.at?.slice(0, 19)}</span> · <b>{a.kind}</b> · {a.text} <code className="text-xs text-ink-faint">{a.corr}</code></div>)}{!rows.length && <Empty title="No activity yet" sub="Configuration changes will appear here." />}</Card></div>
}
export function Audit() {
  const [rows, setRows] = useState([])
  useEffect(() => { api('/audit').then(setRows).catch(() => {}); }, [])
  return <div><PageHead title="Audit log" /><Card>{rows.slice(0, 80).map(a => <div key={a.id} className="text-sm py-1.5 border-t border-slate-100 font-mono text-xs">{a.at?.slice(0, 19)} · {a.action} · {a.entity} #{a.entity_id} · {a.correlation_id}</div>)}</Card></div>
}
