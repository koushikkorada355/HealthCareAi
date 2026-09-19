import React, { useEffect, useMemo, useState } from 'react'
import { api } from '../../api/client.js'
import { Card, Empty } from '../../components/ui.jsx'

const MODES = [
  { id: 'in_person', label: 'In person' },
  { id: 'video', label: 'Video call' },
  { id: 'phone', label: 'Phone call' },
]

const SESSIONS = [
  { id: 'any', label: 'Any time', test: () => true },
  { id: 'morning', label: 'Morning · before 12', test: (d) => d.getHours() < 12 },
  { id: 'afternoon', label: 'Afternoon · 12–5', test: (d) => d.getHours() >= 12 && d.getHours() < 17 },
  { id: 'evening', label: 'Evening · 5+', test: (d) => d.getHours() >= 17 },
]

/* Unified slot picker: one fetch, local date/session/mode filters.
 * Used by the book flow and the classic availability page.
 */
export default function SlotPicker({ doctorId, dayPref = 'Any day', onPick, compact = false }) {
  const [slots, setSlots] = useState([]); const [loading, setLoading] = useState(true)
  const [day, setDay] = useState(''); const [session, setSession] = useState('any'); const [mode, setMode] = useState('in_person')
  const [selected, setSelected] = useState(null)

  useEffect(() => {
    setLoading(true)
    api(`/availability?doctor_id=${doctorId}&days_ahead=14`).then(r => setSlots(r?.slots || [])).catch(() => {}).finally(() => setLoading(false))
  }, [doctorId])

  const days = useMemo(() => {
    const seen = []
    const keys = new Set()
    for (const s of slots) {
      const d = new Date(s.starts_at)
      const k = d.toDateString()
      if (keys.has(k)) continue
      keys.add(k)
      seen.push({ key: k, weekday: d.toLocaleDateString([], { weekday: 'short' }), label: d.toLocaleDateString([], { month: 'short', day: 'numeric' }), count: 0 })
    }
    const counts = {}
    slots.forEach(s => { counts[new Date(s.starts_at).toDateString()] = (counts[new Date(s.starts_at).toDateString()] || 0) + 1 })
    seen.forEach(d => { d.count = counts[d.key] || 0 })
    // honor an incoming day preference on first load
    return seen.slice(0, 14)
  }, [slots])

  useEffect(() => {
    if (!dayPref || dayPref === 'Any day' || day) return
    const t = new Date()
    if (dayPref === 'Today') setDay(t.toDateString())
    else if (dayPref === 'Tomorrow') { const tm = new Date(); tm.setDate(tm.getDate() + 1); setDay(tm.toDateString()) }
  }, [dayPref]) // eslint-disable-line react-hooks/exhaustive-deps

  const visible = useMemo(() => {
    const test = SESSIONS.find(s => s.id === session)?.test || (() => true)
    return slots.filter(s => {
      const d = new Date(s.starts_at)
      if (day && d.toDateString() !== day) return false
      return test(d)
    })
  }, [slots, day, session])

  const pick = (s) => {
    setSelected(s)
    onPick?.(s, mode)
  }

  return <div>
    <div className="flex flex-wrap items-center gap-2 mb-3">
      <div className="flex gap-1.5 overflow-x-auto pb-1 max-w-full" role="tablist" aria-label="Pick a day">
        <button type="button" onClick={() => setDay('')} className={!day ? 'btn-primary text-xs shrink-0' : 'btn-ghost text-xs shrink-0'}>All days</button>
        {days.map(d => <button key={d.key} type="button" role="tab" aria-selected={day === d.key} onClick={() => setDay(day === d.key ? '' : d.key)} className={day === d.key ? 'btn-primary text-xs shrink-0' : 'btn-ghost text-xs shrink-0'}>{d.weekday} {d.label} · {d.count}</button>)}
      </div>
    </div>
    <div className="flex flex-wrap gap-2 mb-3">
      {SESSIONS.map(s => <button key={s.id} type="button" onClick={() => setSession(s.id)} className={session === s.id ? 'btn-primary text-xs' : 'btn-ghost text-xs'}>{s.label}</button>)}
      <select aria-label="Visit mode" className="input !w-auto !py-1.5 text-xs" value={mode} onChange={e => setMode(e.target.value)}>{MODES.map(m => <option key={m.id} value={m.id}>{m.label}</option>)}</select>
    </div>
    {loading ? (
      <div className="grid gap-3 sm:grid-cols-2 md:grid-cols-3">{[0, 1, 2, 3, 4, 5].map(i => <div key={i} className="card p-4"><div className="skeleton h-5 w-2/3" /><div className="skeleton mt-2 h-4 w-1/2" /></div>)}</div>
    ) : visible.length ? (
      <div className={`grid gap-3 ${compact ? 'sm:grid-cols-2' : 'sm:grid-cols-2 md:grid-cols-3'}`}>
        {visible.slice(0, 30).map(s => {
          const key = `${s.calendar_id}-${s.starts_at}`
          const active = selected?.starts_at === s.starts_at && selected?.calendar_id === s.calendar_id
          const d = new Date(s.starts_at)
          return <button key={key} type="button" onClick={() => pick(s)} className={`card card-hover !p-4 text-left ${active ? '!border-brand !ring-2 !ring-brand/30' : ''}`}>
            <div className="font-extrabold">{d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</div>
            <div className="text-xs text-ink-soft">{d.toLocaleDateString([], { weekday: 'long', month: 'short', day: 'numeric' })} · verified slot</div>
            <div className={`mt-2 text-xs font-bold ${active ? 'text-brand-deep' : 'text-brand'}`}>{active ? '✓ Selected — continue ↓' : 'Select →'}</div>
          </button>
        })}
      </div>
    ) : <Card><Empty title="No slots match these filters" sub="Try another day, session or mode. Blocked time, leave and bookings are respected." /></Card>}
  </div>
}
