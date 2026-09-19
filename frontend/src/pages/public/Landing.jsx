import React from 'react'
import { Link } from 'react-router-dom'
import { HERO_IMG, HOSPITAL_COVERS } from '../../utils/photos.js'

const STEPS = ['Patient request', 'AI understanding + context', 'Real availability', 'Authorized action (MCP)', 'EHR integration', 'External verification', 'State sync', 'Questionnaire + workflow', 'Doctor + admin visibility']
const PROOFS = [
  ['Real slots only', 'Every option comes from the scheduling engine — blocks, leave and conflicts respected.'],
  ['Verified before confirmed', 'No “booked!” until the external record is read back and matched.'],
  ['Failure-safe', 'Timeout → probe → sync without duplicates, visible to ops.'],
  ['Tenant-isolated', 'Hospital A never sees Hospital B data. Enforced server-side.'],
]

export default function Landing() {
  return (
    <div className="min-h-screen">
      <header className="mx-auto flex max-w-6xl items-center justify-between p-5 animate-fade-in">
        <div className="flex items-center gap-2.5">
          <div className="flex h-10 w-10 items-center justify-center rounded-2xl bg-gradient-to-br from-brand to-brand-deep text-white shadow-lift">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="h-5 w-5"><path d="M12 5v14M5 12h14" /></svg>
          </div>
          <div><div className="font-display text-lg font-semibold leading-none">MediConnect</div><div className="text-[11px] text-ink-soft">AI-native hospital scheduling</div></div>
        </div>
        <div className="flex gap-2"><Link to="/login" className="btn-ghost text-sm">Sign in</Link><Link to="/register" className="btn-primary text-sm">Get care</Link></div>
      </header>

      <main className="mx-auto max-w-6xl px-5 pb-16">
        <div className="grid items-center gap-8 md:grid-cols-2">
          <div className="animate-fade-up">
            <div className="pill bg-brand-soft text-brand-ink mb-4">✦ AI-native · Verified bookings · Mock-EHR integrated</div>
            <h1 className="font-display text-4xl leading-[1.08] md:text-[52px]">Care, booked in <em className="bg-gradient-to-r from-brand to-apricot bg-clip-text not-italic text-transparent">one conversation</em>.</h1>
            <p className="mt-4 max-w-lg text-ink-soft">Describe your need in plain words. The assistant checks <b>real availability</b>, books through controlled capabilities, verifies against the health system, and syncs — never inventing slots.</p>
            <div className="mt-6 flex flex-wrap gap-2">
              <Link to="/register" className="btn-primary">Start as patient</Link>
              <Link to="/hospitals/apply" className="btn-ghost">Register hospital</Link>
              <Link to="/login" className="btn-ghost">Demo logins</Link>
            </div>
            <div className="card mt-6 p-4 text-sm card-hover">
              <div className="text-[11px] font-bold tracking-wider text-ink-faint">TRY SAYING</div>
              <div className="mt-1 font-display text-[17px] italic">“I need to see a doctor for my shoulder pain sometime this week.”</div>
              <div className="mt-2 text-xs text-ink-soft">→ intent: book · specialty: orthopedics → real slots → verified confirmation. The AI never diagnoses.</div>
            </div>
          </div>
          <div className="relative animate-fade-up" style={{ animationDelay: '120ms' }}>
            <div className="overflow-hidden rounded-2xl shadow-lift animate-float">
              <img src={HERO_IMG} alt="Doctor using tablet" className="h-72 w-full object-cover md:h-80" loading="eager" onError={(e) => { e.currentTarget.style.display = 'none' }} />
            </div>
            <div className="card absolute -bottom-6 -left-2 p-4 md:-left-6 animate-pop-in" style={{ animationDelay: '300ms' }}>
              <div className="text-[11px] font-bold tracking-wider text-mint-deep">● LIVE VERIFICATION</div>
              <div className="text-sm font-bold">Appointment #8 · confirmed</div>
              <div className="font-mono text-[11px] text-ink-soft">EHR matched · synced · ref e1e3e806224d</div>
            </div>
          </div>
        </div>

        <div className="card hero-gradient mt-14 border-0 p-6 text-white md:p-8">
          <div className="text-xs font-bold tracking-widest opacity-80">THE BOOKING CHAIN — EVERY STEP REAL, EVERY STEP VISIBLE</div>
          <div className="stagger mt-4 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {STEPS.map((s, i) => (
              <div key={s} className="flex items-center gap-3 rounded-xl bg-white/12 px-3 py-2.5 backdrop-blur transition hover:bg-white/20">
                <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-full bg-white font-extrabold text-brand-ink text-xs">{i + 1}</div>
                <div className="text-sm font-semibold">{s}</div>
              </div>
            ))}
          </div>
        </div>

        <div className="stagger mt-8 grid gap-4 md:grid-cols-4">
          {PROOFS.map(([t, d]) => (
            <div key={t} className="card card-hover p-5"><div className="font-bold">{t}</div><div className="mt-1 text-sm text-ink-soft">{d}</div></div>
          ))}
        </div>

        <div className="mt-8 grid gap-4 md:grid-cols-3">
          {HOSPITAL_COVERS.map((c, i) => (
            <div key={i} className="group relative h-40 overflow-hidden rounded-2xl shadow-card">
              <img src={c} alt="Hospital" loading="lazy" className="h-full w-full object-cover transition duration-500 group-hover:scale-105" onError={(e) => { e.currentTarget.style.display = 'none' }} />
              <div className="absolute inset-0 bg-gradient-to-t from-brand-ink/70 to-transparent" />
              <div className="absolute bottom-3 left-4 font-display font-semibold text-white">{['CityCare General', 'Riverside Specialty', 'Northgate Community'][i]}</div>
            </div>
          ))}
        </div>
      </main>
    </div>
  )
}
