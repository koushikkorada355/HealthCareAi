import React, { useState } from 'react'
import { NavLink } from 'react-router-dom'
import { doctorPhoto } from '../utils/photos.js'

export const STATUS_COLORS = {
  confirmed: 'bg-emerald-50 text-emerald-700', pending: 'bg-amber-50 text-amber-700',
  requested: 'bg-sky-50 text-sky-700', sync_pending: 'bg-amber-50 text-amber-700',
  cancelled: 'bg-slate-100 text-slate-500', completed: 'bg-brand-soft text-brand-ink',
  failed: 'bg-red-50 text-red-600', rescheduled: 'bg-violet-50 text-violet-700',
  no_show: 'bg-orange-50 text-orange-700', reconciliation_required: 'bg-red-50 text-red-700',
  synced: 'bg-emerald-50 text-emerald-700', unknown_outcome: 'bg-red-50 text-red-700',
  verification_pending: 'bg-amber-50 text-amber-700', approved: 'bg-emerald-50 text-emerald-700',
  submitted: 'bg-sky-50 text-sky-700', under_review: 'bg-amber-50 text-amber-700',
  rejected: 'bg-red-50 text-red-600', active: 'bg-emerald-50 text-emerald-700',
  success: 'bg-emerald-50 text-emerald-700', open: 'bg-red-50 text-red-700',
  resolved: 'bg-emerald-50 text-emerald-700', escalated: 'bg-orange-50 text-orange-700',
  running: 'bg-sky-50 text-sky-700', sent: 'bg-emerald-50 text-emerald-700',
}
export function Pill({ value }) {
  const c = STATUS_COLORS[String(value || '').toLowerCase()] || 'bg-slate-100 text-slate-600'
  return <span className={`pill ${c}`}><span className="w-1.5 h-1.5 rounded-full bg-current" />{String(value).replace(/_/g, ' ')}</span>
}
export function Card({ className = '', children }) { return <div className={`card p-5 ${className}`}>{children}</div> }
export function PageHead({ title, sub, right }) {
  return <div className="flex flex-wrap items-end justify-between gap-3 mb-5 animate-fade-up">
    <div><h1 className="font-display text-2xl md:text-[28px] font-semibold tracking-tight">{title}</h1>{sub && <p className="text-sm text-ink-soft mt-1">{sub}</p>}</div>
    <div className="flex gap-2">{right}</div>
  </div>
}
export function Stat({ label, value, accent }) {
  return <Card className="card-hover"><div className="text-[11px] font-bold tracking-wider text-ink-faint">{label.toUpperCase()}</div>
    <div className={`text-3xl font-extrabold mt-1 ${accent || ''}`}>{value ?? '–'}</div></Card>
}
export function Empty({ title, sub }) {
  return <div className="text-center py-12 animate-fade-in">
    <svg width="72" height="72" viewBox="0 0 72 72" className="mx-auto mb-3 opacity-80"><rect x="14" y="10" width="44" height="52" rx="12" fill="#E4EEFE" /><path d="M24 30h24M24 38h24M24 46h14" stroke="#1E6FF5" strokeWidth="3" strokeLinecap="round" /></svg>
    <div className="font-semibold">{title}</div><div className="text-sm text-ink-soft">{sub}</div>
  </div>
}
export function Skeleton({ className = 'h-4' }) { return <div className={`skeleton rounded-lg ${className}`} /> }
export function SideLink({ to, children }) {
  return <NavLink to={to} end={to.split('/').length <= 2} className={({ isActive }) => `side-link ${isActive ? 'active' : ''}`}>{children}</NavLink>
}
/* Avatar: initials by default (plain). Pass a photo URL to show a picture instead. */
export function Avatar({ name, size = 40, photo, seed, plain = true }) {
  const [failed, setFailed] = useState(false)
  const src = plain ? null : (photo || doctorPhoto(seed ?? name, null))
  const hues = [[217, 45], [210, 50], [160, 40], [24, 70], [262, 45], [330, 50]]
  const [h, s] = hues[(name || 'x').length % hues.length]
  const initials = (name || '?').split(' ').map(w => w[0]).slice(0, 2).join('').toUpperCase()
  if (!failed && src) {
    return <img src={src} alt={name} loading="lazy" onError={() => setFailed(true)} className="rounded-full object-cover shrink-0 ring-2 ring-white shadow-card" style={{ width: size, height: size }} />
  }
  return <div className="rounded-full flex items-center justify-center font-bold text-white shrink-0" style={{ width: size, height: size, background: `linear-gradient(135deg, hsl(${h} ${s}% 55%), hsl(${h + 25} ${s}% 38%))`, fontSize: size * 0.36 }}>{initials}</div>
}
/* Cover banner with photo + gradient overlay, photo fallback hides img. */
export function Cover({ src, height = 96, children }) {
  const [failed, setFailed] = useState(false)
  return <div className="relative -m-5 mb-4 overflow-hidden rounded-t-2xl hero-gradient" style={{ height }}>
    {!failed && src && <img src={src} alt="" loading="lazy" onError={() => setFailed(true)} className="absolute inset-0 h-full w-full object-cover" />}
    <div className="absolute inset-0 bg-gradient-to-t from-brand-ink/60 to-transparent" />
    {children && <div className="absolute bottom-2 left-4 right-4">{children}</div>}
  </div>
}
export function Trace({ items }) {
  if (!items?.length) return null
  return <details className="mt-2 text-xs bg-slate-50 border border-slate-100 rounded-xl p-2.5">
    <summary className="cursor-pointer font-semibold text-ink-soft">How the AI worked (trace)</summary>
    <ul className="mt-1.5 space-y-1 font-mono text-[11px] text-slate-600">{items.map((t, i) => <li key={i}>→ {t}</li>)}</ul>
  </details>
}
