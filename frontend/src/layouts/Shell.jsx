import React, { useState } from 'react'
import { Link, useNavigate, useLocation } from 'react-router-dom'
import { useAuth } from '../context/AuthContext.jsx'
import { SideLink, Avatar } from '../components/ui.jsx'

/* Minimal inline icon set for the template sidebar. */
const I = {
  dash: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]"><rect x="3" y="3" width="7" height="9" rx="1.5" /><rect x="14" y="3" width="7" height="5" rx="1.5" /><rect x="14" y="12" width="7" height="9" rx="1.5" /><rect x="3" y="16" width="7" height="5" rx="1.5" /></svg>,
  cal: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]"><rect x="3" y="5" width="18" height="16" rx="2" /><path d="M8 3v4M16 3v4M3 10h18" /></svg>,
  chat: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]"><path d="M21 12a8 8 0 0 1-8 8H4l2-3a8 8 0 1 1 15-5z" /></svg>,
  mic: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]"><rect x="9" y="3" width="6" height="11" rx="3" /><path d="M5 11a7 7 0 0 0 14 0M12 18v3" /></svg>,
  doc: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]"><circle cx="12" cy="8" r="4" /><path d="M4 21c0-4 3.6-6 8-6s8 2 8 6" /></svg>,
  hosp: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]"><path d="M4 21V7l8-4 8 4v14M12 9v6M9 12h6M4 21h16" /></svg>,
  clip: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]"><rect x="6" y="4" width="12" height="17" rx="2" /><path d="M9 4a3 3 0 0 1 6 0M9 11h6M9 15h4" /></svg>,
  pulse: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]"><path d="M3 12h4l3 8 4-16 3 8h4" /></svg>,
  gear: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]"><circle cx="12" cy="12" r="3" /><path d="M19 12a7 7 0 0 0-.1-1.2l2-1.6-2-3.4-2.4 1a7 7 0 0 0-2-1.2L14 3h-4l-.5 2.6a7 7 0 0 0-2 1.2l-2.4-1-2 3.4 2 1.6A7 7 0 0 0 5 12c0 .4 0 .8.1 1.2l-2 1.6 2 3.4 2.4-1a7 7 0 0 0 2 1.2L10 21h4l.5-2.6a7 7 0 0 0 2-1.2l2.4 1 2-3.4-2-1.6c.07-.4.1-.8.1-1.2z" /></svg>,
  bell: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]"><path d="M18 8a6 6 0 1 0-12 0c0 7-3 8-3 8h18s-3-1-3-8M10 21a2 2 0 0 0 4 0" /></svg>,
  chart: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]"><path d="M4 20V10M10 20V4M16 20v-8M22 20H2" /></svg>,
  shield: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]"><path d="M12 3l8 3v6c0 5-3.5 8-8 9-4.5-1-8-4-8-9V6l8-3z" /></svg>,
  users: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]"><circle cx="9" cy="8" r="3.5" /><path d="M2.5 20c0-3.5 3-5.5 6.5-5.5s6.5 2 6.5 5.5M16 5a3.5 3.5 0 0 1 0 7M17.5 14.7c2.4.7 4 2.3 4 5.3" /></svg>,
  inbox: <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" className="h-[18px] w-[18px]"><path d="M22 12h-6l-2 3h-4l-2-3H2M5 5h14l3 7v7H2v-7l3-7z" /></svg>,
}

const NAV = {
  platform_admin: [['Dashboard', '/admin', 'dash'], ['Applications', '/admin/applications', 'inbox'], ['Hospitals', '/admin/hospitals', 'hosp'], ['Doctors', '/admin/doctors', 'doc'], ['Patients', '/admin/patients', 'users'], ['Appointments', '/admin/appointments', 'cal'], ['AI Activity', '/admin/ai', 'chat'], ['Analytics', '/admin/analytics', 'chart'], ['Audit', '/admin/audit', 'clip'], ['Ops Health', '/admin/ops', 'pulse']],
  hospital_admin: [['Dashboard', '/hospital', 'dash'], ['Hospital', '/hospital/profile', 'hosp'], ['Doctors', '/hospital/doctors', 'doc'], ['Schedules', '/hospital/schedules', 'cal'], ['Appointments', '/hospital/appointments', 'clip'], ['Questionnaires', '/hospital/questionnaires', 'clip'], ['AI Activity', '/hospital/ai', 'chat'], ['Integrations', '/hospital/integrations', 'pulse'], ['Workflows', '/hospital/workflows', 'gear'], ['Notifications', '/hospital/notifications', 'bell'], ['Reviews', '/hospital/reviews', 'chat'], ['Activity', '/hospital/activity', 'clip'], ['Analytics', '/hospital/analytics', 'chart'], ['Audit', '/hospital/audit', 'shield']],
  doctor: [['Dashboard', '/doctor', 'dash'], ['Today', '/doctor/today', 'cal'], ['Upcoming', '/doctor/upcoming', 'clip'], ['Calendar', '/doctor/calendar', 'cal'], ['Availability', '/doctor/availability', 'gear'], ['Appointments', '/doctor/appointments', 'inbox']],
  patient: [['Home', '/app', 'dash'], ['Book Visit', '/app/book', 'cal'], ['AI Assistant', '/app/assistant', 'chat'], ['Voice', '/app/voice', 'mic'], ['Find Doctors', '/app/doctors', 'doc'], ['Hospitals', '/app/hospitals', 'hosp'], ['Upcoming', '/app/upcoming', 'cal'], ['History', '/app/history', 'clip'], ['Questionnaires', '/app/questionnaires', 'clip'], ['Preferences', '/app/preferences', 'gear'], ['Profile', '/app/profile', 'users']],
}

const ROLE_META = {
  platform_admin: { label: 'System Admin', chip: 'bg-white/15 text-white', bar: 'from-brand-ink via-brand-deep to-brand' },
  hospital_admin: { label: 'Hospital admin', chip: 'bg-brand-soft text-brand-ink', bar: 'from-brand-deep via-brand to-apricot' },
  doctor: { label: 'Doctor', chip: 'bg-mint-soft text-mint-deep', bar: 'from-mint-deep via-mint to-brand' },
  patient: { label: 'Patient', chip: 'bg-apricot-soft text-apricot-deep', bar: 'from-brand via-[#5B9BFF] to-apricot' },
}

export default function Shell({ children }) {
  const { user, logout } = useAuth()
  const nav = useNavigate()
  const loc = useLocation()
  const [mobileOpen, setMobileOpen] = useState(false)
  const links = NAV[user?.role] || []
  const meta = ROLE_META[user?.role] || ROLE_META.patient
  const crumb = links.find(([, to]) => loc.pathname === to || (to !== '/app' && to !== '/doctor' && to !== '/hospital' && to !== '/admin' && loc.pathname.startsWith(to)))?.[0] || meta.label

  const side = (onNav) => (
    <>
      <Link to="/" onClick={onNav} className="flex items-center gap-2.5 px-2 py-3 mb-2">
        <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-brand to-brand-deep text-white shadow-lift">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="h-5 w-5"><path d="M12 5v14M5 12h14" /></svg>
        </div>
        <div>
          <div className="font-display text-[17px] font-semibold leading-none">MediConnect</div>
          <div className={`mt-1 inline-block rounded-full px-2 py-0.5 text-[10px] font-bold ${meta.chip}`}>{meta.label}</div>
        </div>
      </Link>
      <nav className="flex flex-col gap-0.5 overflow-auto pr-1">
        {links.map(([l, to, icon]) => (
          <span key={to} onClick={onNav}><SideLink to={to}><span className="opacity-80">{I[icon] || I.dash}</span>{l}</SideLink></span>
        ))}
      </nav>
      <div className="mt-auto rounded-2xl bg-gradient-to-br from-brand-soft to-apricot-soft p-3 text-xs text-ink-soft">
        Need help booking? <Link to="/app/assistant" className="font-bold text-brand-deep">Ask the AI assistant →</Link>
      </div>
      <div className="flex items-center gap-2.5 px-2 pt-3">
        <Avatar name={user?.full_name} size={34} seed={user?.id} />
        <div className="min-w-0 flex-1"><div className="truncate text-sm font-semibold">{user?.full_name}</div><div className="truncate text-xs text-ink-faint">{user?.email}</div></div>
        <button onClick={() => { logout(); nav('/login') }} className="text-xs font-bold text-crit hover:underline">Exit</button>
      </div>
    </>
  )

  return (
    <div className="min-h-screen">
      {/* role-tinted top accent */}
      <div className={`h-1.5 bg-gradient-to-r ${meta.bar}`} />
      <div className="flex">
        <aside className="hidden w-64 shrink-0 flex-col border-r border-slate-100 bg-white/80 p-4 backdrop-blur md:flex" style={{ minHeight: 'calc(100vh - 6px)' }}>
          {side(null)}
        </aside>
        <div className="min-w-0 flex-1">
          {/* mobile bar */}
          <div className="sticky top-0 z-20 flex items-center gap-2 border-b border-slate-100 bg-white/90 p-3 backdrop-blur md:hidden">
            <button onClick={() => setMobileOpen(true)} aria-label="Open menu" className="btn-ghost !px-3 !py-1.5 text-sm">☰</button>
            <span className="font-display font-semibold">MediConnect</span>
            <button onClick={() => { logout(); nav('/login') }} className="ml-auto text-xs font-bold text-crit">Exit</button>
          </div>
          {/* desktop breadcrumb bar */}
          <div className="sticky top-0 z-10 hidden items-center gap-2 border-b border-slate-100 bg-white/70 px-7 py-2.5 text-xs text-ink-faint backdrop-blur md:flex">
            <span>MediConnect</span><span>/</span><span className="font-bold text-ink">{crumb}</span>
            <span className="ml-auto rounded-full bg-mint-soft px-2.5 py-0.5 font-bold text-mint-deep">EHR verified bookings</span>
          </div>
          <main key={loc.pathname} className="mx-auto max-w-6xl animate-fade-up p-4 md:p-7">{children}</main>
        </div>
      </div>
      {/* mobile drawer */}
      {mobileOpen && (
        <div className="fixed inset-0 z-30 md:hidden">
          <div className="absolute inset-0 bg-ink/40 animate-fade-in" onClick={() => setMobileOpen(false)} />
          <div className="absolute left-0 top-0 flex h-full w-72 flex-col bg-white p-4 animate-slide-in">{side(() => setMobileOpen(false))}</div>
        </div>
      )}
    </div>
  )
}
