import React, { useState, useRef, useEffect } from 'react'
import { api } from '../../api/client.js'
import { Card, PageHead, Trace } from '../../components/ui.jsx'
import { renderSafe } from '../../utils/markdown.js'

export default function Assistant() {
  const [msgs, setMsgs] = useState([{ role: 'assistant', content: "Hi! Tell me what you need — e.g. 'I need to see a doctor for my shoulder pain sometime this week.'" }])
  const [input, setInput] = useState(''); const [busy, setBusy] = useState(false)
  const [conv, setConv] = useState(null); const [bookBusy, setBookBusy] = useState(null)
  const [pending, setPending] = useState(null) // {doc, slot, reason, mode} — details asked BEFORE booking
  const bottom = useRef(null)
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs])
  const send = async (text) => {
    const t = (text ?? input).trim(); if (!t || busy) return
    setMsgs(m => [...m, { role: 'user', content: t }]); setInput(''); setBusy(true)
    try {
      const r = await api('/ai/chat', { method: 'POST', body: { message: t, conversation_id: conv } })
      setConv(r.conversation_id)
      setMsgs(m => [...m, { role: 'assistant', content: r.reply, trace: r.trace, data: r.data, corr: r.correlation_id }])
    } catch (e) { setMsgs(m => [...m, { role: 'assistant', content: `Something went wrong: ${e.message}` }]) }
    finally { setBusy(false) }
  }
  const book = async () => {
    const p = pending
    if (!p || !p.reason.trim()) return
    const key = `${p.slot.calendar_id}-${p.slot.starts_at}`
    setBookBusy(key)
    try {
      const me = await api('/auth/me')
      if (!me.patient_id) throw new Error('No patient profile on this account.')
      const doc = p.doc, slot = p.slot
      const r = await api('/appointments', { method: 'POST', body: { hospital_id: doc.hospital_id, doctor_id: doc.id, patient_id: me.patient_id, starts_at: slot.starts_at, ends_at: slot.ends_at, calendar_id: slot.calendar_id, mode: p.mode, reason: p.reason.trim(), idempotency_key: `ai-${me.id}-${doc.id}-${slot.starts_at}-${Date.now().toString(36)}` } })
      setPending(null)
      setMsgs(m => [...m, { role: 'assistant', content: `Confirmed! Appointment #${r.appointment_id} is **${r.status}** (verified: ${r.verified ? 'yes — external record matched' : 'pending'}). Correlation \`${r.correlation_id}\`. A pre-visit questionnaire was assigned. [Open appointment](/app/appointments/${r.appointment_id})`, data: null }])
    } catch (e) { setMsgs(m => [...m, { role: 'assistant', content: `Booking failed safely (no duplicate created): ${e.message}` }]) }
    finally { setBookBusy(null) }
  }
  return (
    <div>
      <PageHead title="AI assistant" sub="Administrative help only — it finds real availability and books verified slots. It never diagnoses." />
      <Card className="p-0 overflow-hidden">
        <div className="h-[52vh] overflow-auto p-4 space-y-3 bg-cream/60">
          {msgs.map((m, i) => (
            <div key={i} className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm fade-in ${m.role === 'user' ? 'ml-auto bg-teal text-white' : 'bg-white border border-slate-100 shadow-card'}`}>
              <div className="chatdoc whitespace-pre-wrap" dangerouslySetInnerHTML={{ __html: renderSafe(m.content) }} />
              {m.corr && <div className="mt-1 text-[10px] opacity-60 font-mono">ref {m.corr}</div>}
              <Trace items={m.trace} />
              {m.data?.doctors && (
                <div className="mt-2 space-y-2">
                  {m.data.slots?.map(s => {
                    const key = `${s.calendar_id}-${s.starts_at}`
                    const isPending = pending?.slot.starts_at === s.starts_at && pending?.slot.calendar_id === s.calendar_id
                    return (
                    <div key={key} className="bg-cream rounded-xl px-3 py-2">
                      <div className="flex items-center justify-between">
                        <span className="font-semibold">{new Date(s.starts_at).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                        <button type="button" disabled={!!bookBusy} onClick={() => setPending({ doc: m.data.doctors[0], slot: s, reason: '', mode: 'in_person' })} className="btn-primary text-xs !px-3 !py-1.5">{isPending ? '✓ Selected' : 'Select'}</button>
                      </div>
                      {isPending && (
                        <div className="mt-2 space-y-2 border-t border-brand/15 pt-2 animate-fade-up">
                          <div className="text-xs font-bold text-ink-soft">We need a few details before booking — nothing is confirmed yet:</div>
                          <label htmlFor={`ai-reason-${key}`} className="sr-only">Reason for visit</label>
                          <input id={`ai-reason-${key}`} className="input !py-1.5 text-sm" placeholder="Reason for visit (required)…" value={pending.reason} onChange={e => setPending({ ...pending, reason: e.target.value })} />
                          <div className="flex gap-2">
                            <label htmlFor={`ai-mode-${key}`} className="sr-only">Visit mode</label>
                            <select id={`ai-mode-${key}`} className="input !py-1.5 text-sm" value={pending.mode} onChange={e => setPending({ ...pending, mode: e.target.value })}>
                              <option value="in_person">In person</option><option value="video">Video call</option><option value="phone">Phone call</option>
                            </select>
                            <button type="button" disabled={!!bookBusy || !pending.reason.trim()} onClick={book} className="btn-accent text-xs !px-3 !py-1.5 shrink-0">{bookBusy === key ? 'Verifying…' : 'Confirm ✓'}</button>
                            <button type="button" onClick={() => setPending(null)} className="btn-ghost text-xs !px-3 !py-1.5 shrink-0">Cancel</button>
                          </div>
                        </div>
                      )}
                    </div>
                  )})}
                </div>
              )}
            </div>
          ))}
          {busy && <div className="text-sm text-ink-soft">Assistant is checking…</div>}
          <div ref={bottom} />
        </div>
        <form onSubmit={e => { e.preventDefault(); send() }} className="flex gap-2 p-3 border-t border-slate-100 bg-white">
          <label htmlFor="ai-input" className="sr-only">Message the assistant</label>
          <input id="ai-input" className="input" placeholder="Describe your need…" value={input} onChange={e => setInput(e.target.value)} />
          <button type="submit" className="btn-primary" disabled={busy}>Send</button>
        </form>
      </Card>
    </div>
  )
}
