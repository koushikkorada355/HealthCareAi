import React, { useState } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import { useAuth, DEMOS } from '../../context/AuthContext.jsx'

export function Login() {
  const { login } = useAuth(); const nav = useNavigate()
  const [email, setEmail] = useState('aarav@example.org'); const [password, setPassword] = useState('password123')
  const [err, setErr] = useState(''); const [busy, setBusy] = useState(false)
  const go = async (e) => { e?.preventDefault(); setBusy(true); setErr(''); try { const u = await login(email, password); nav(u.role === 'platform_admin' ? '/admin' : u.role === 'hospital_admin' ? '/hospital' : u.role === 'doctor' ? '/doctor' : '/app') } catch (ex) { setErr(ex.message) } finally { setBusy(false) } }
  return (
    <div className="min-h-screen flex items-center justify-center p-5">
      <form onSubmit={go} className="card p-7 w-full max-w-md fade-in">
        <div className="font-display text-2xl mb-1">Welcome back</div>
        <p className="text-sm text-ink-soft mb-5">Sign in to your MediConnect workspace.</p>
        <label className="text-xs font-semibold">Email</label><input className="input mt-1 mb-3" value={email} onChange={e => setEmail(e.target.value)} />
        <label className="text-xs font-semibold">Password</label><input className="input mt-1 mb-3" type="password" value={password} onChange={e => setPassword(e.target.value)} />
        {err && <div className="text-sm text-crit bg-red-50 rounded-xl p-2.5 mb-3">{err}</div>}
        <button className="btn-primary w-full" disabled={busy}>{busy ? 'Signing in…' : 'Sign in'}</button>
        <div className="mt-4 text-xs font-bold text-ink-soft">ONE-CLICK DEMO ACCOUNTS (System Admin: 12345, others: password123)</div>
        <div className="grid grid-cols-2 gap-2 mt-2">{DEMOS.map(d => <button type="button" key={d.email} onClick={() => { setEmail(d.email); setPassword(d.password || 'password123') }} className="btn-ghost text-xs">{d.label}</button>)}</div>
        <div className="mt-4 text-sm flex justify-between"><Link to="/register" className="text-teal font-semibold">Create account</Link><Link to="/forgot-password" className="text-ink-soft">Forgot password?</Link></div>
      </form>
    </div>
  )
}
export function Register() {
  const { register } = useAuth(); const nav = useNavigate()
  const [f, setF] = useState({ full_name: '', email: '', password: 'password123', phone: '' })
  const [err, setErr] = useState('')
  const go = async (e) => { e.preventDefault(); setErr(''); try { await register({ ...f, role: 'patient' }); nav('/app') } catch (ex) { setErr(ex.message) } }
  return (
    <div className="min-h-screen flex items-center justify-center p-5">
      <form onSubmit={go} className="card p-7 w-full max-w-md fade-in">
        <div className="font-display text-2xl mb-1">Create patient account</div>
        <p className="text-sm text-ink-soft mb-5">Book verified appointments in minutes.</p>
        {[['full_name', 'Full name'], ['email', 'Email'], ['phone', 'Phone'], ['password', 'Password']].map(([k, l]) => (
          <div key={k} className="mb-3"><label className="text-xs font-semibold">{l}</label>
          <input className="input mt-1" type={k === 'password' ? 'password' : 'text'} value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })} required={k !== 'phone'} /></div>
        ))}
        {err && <div className="text-sm text-crit bg-red-50 rounded-xl p-2.5 mb-3">{err}</div>}
        <button className="btn-primary w-full">Create account</button>
        <div className="mt-3 text-sm text-center"><Link to="/login" className="text-teal font-semibold">Have an account? Sign in</Link></div>
      </form>
    </div>
  )
}
export function Forgot() {
  const [done, setDone] = useState(false)
  return <div className="min-h-screen flex items-center justify-center p-5"><div className="card p-7 w-full max-w-md">
    <div className="font-display text-2xl mb-1">Reset password</div>
    {!done ? <form onSubmit={e => { e.preventDefault(); setDone(true) }}><input className="input mt-4 mb-3" placeholder="you@example.org" required /><button className="btn-primary w-full">Send reset link</button></form>
    : <div className="mt-4 text-sm bg-emerald-50 text-emerald-700 rounded-xl p-3">If the account exists, a reset link was sent (demo).</div>}
  </div></div>
}
export function HospitalApply() {
  const [step, setStep] = useState(0); const [f, setF] = useState({ name: '', city: '', address: '', phone: '', contact_email: '' }); const [done, setDone] = useState(null); const [busy, setBusy] = useState(false)
  const submit = async (asDraft) => {
    const { api, token } = await import('../../api/client.js')
    if (!token()) { setDone({ error: 'Please login first as a hospital admin, then apply.' }); return }
    setBusy(true)
    try { const r = await api('/hospitals/apply', { method: 'POST', body: { ...f, services: ['outpatient'], operating_hours: {}, as_draft: !!asDraft } }); setDone(r) }
    catch (e) { setDone({ error: e.message }) } finally { setBusy(false) }
  }
  return <div className="min-h-screen flex items-center justify-center p-5"><div className="card p-7 w-full max-w-lg fade-in">
    <div className="font-display text-2xl">Register hospital</div>
    <p className="text-sm text-ink-soft mb-4">Draft → Submitted → Under review → Approved. Only approved hospitals receive bookings.</p>
    {[['name', 'Hospital name'], ['city', 'City'], ['address', 'Address'], ['phone', 'Phone'], ['contact_email', 'Admin email']].map(([k, l]) => (
      <div key={k} className="mb-3"><label className="text-xs font-semibold">{l}</label><input className="input mt-1" value={f[k]} onChange={e => setF({ ...f, [k]: e.target.value })} /></div>
    ))}
    {!done ? <div className="flex gap-2"><button onClick={() => submit(true)} disabled={busy} className="btn-ghost flex-1">{busy ? 'Saving…' : 'Save draft'}</button><button onClick={() => submit(false)} disabled={busy} className="btn-primary flex-1">{busy ? 'Submitting…' : 'Submit application'}</button></div>
    : done.error ? <div className="text-sm text-crit bg-red-50 p-3 rounded-xl">{done.error}</div>
    : <div className="text-sm bg-emerald-50 text-emerald-700 p-3 rounded-xl">{done.status === 'draft' ? 'Saved as draft.' : 'Submitted!'} Status: <b>{done.status}</b>. Track it under System Admin → Applications.</div>}
  </div></div>
}
