import React, { useEffect, useRef, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { api } from '../../api/client.js'
import { Avatar, Card, Empty, Pill } from '../../components/ui.jsx'
import VoiceOrb from '../../components/VoiceOrb.jsx'
import { isTTSSupported, loadVoices, speakReply, stopSpeaking } from '../../utils/speech.js'

function Bubble({ role, content }) {
  const mine = role === 'user'
  return (
    <div className={`flex ${mine ? 'justify-end' : 'justify-start'}`}>
      <div className={`max-w-[85%] rounded-2xl px-4 py-2.5 text-sm leading-relaxed shadow-sm md-bubble ${mine ? 'bg-brand text-white' : 'bg-white border border-slate-100'}`}>
        {mine ? <div className="whitespace-pre-wrap">{content}</div>
          : <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>}
      </div>
    </div>
  )
}

const PHASES = ['Understanding…', 'Searching…', 'Checking real availability…', 'Verifying…']

function TypingBubble() {
  const [pi, setPi] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setPi(i => (i + 1) % PHASES.length), 4000)
    return () => clearInterval(t)
  }, [])
  return (
    <div className="flex justify-start" aria-live="polite" aria-label="Assistant is typing">
      <div className="max-w-[85%] rounded-2xl px-4 py-2.5 bg-white border border-slate-100 shadow-sm">
        <div className="flex items-center gap-1.5">
          {[0, 1, 2].map(d => (
            <span key={d} className="h-2 w-2 rounded-full bg-brand animate-bounce" style={{ animationDelay: `${d * 0.15}s` }} />
          ))}
        </div>
        <div className="mt-1 text-xs text-ink-faint">{PHASES[pi]}</div>
      </div>
    </div>
  )
}

function Actions({ actions, onTap, busy }) {
  if (!actions?.length) return null
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {actions.map((a, i) => (
        <button key={i} type="button" disabled={busy} onClick={() => onTap(a.text)}
          className="btn-primary text-xs disabled:opacity-50">{a.label}</button>
      ))}
    </div>
  )
}

function Options({ options, onTap, busy }) {
  if (!options?.length) return null
  return (
    <div className="flex flex-wrap gap-1.5 mt-2">
      {options.map((o, i) => (
        <button key={i} type="button" disabled={busy} onClick={() => onTap(o.text)}
          className="btn-ghost text-xs disabled:opacity-50">👉 {o.label}</button>
      ))}
    </div>
  )
}

function Cards({ data, onTap, busy }) {
  if (!data || !data.card) return null
  if (data.card === 'doctors') return (
    <div className="grid md:grid-cols-2 gap-3 mt-2">
      {data.items.map(d => (
        <Card key={d.id} className="card-hover flex gap-3">
          <Avatar name={d.name} size={48} seed={d.id} plain={false} />
          <div className="flex-1 min-w-0">
            <div className="font-bold leading-tight">{d.name}</div>
            <div className="text-xs text-ink-soft">{d.specialty} · {d.hospital_name}</div>
            <div className="mt-1 text-sm"><b>★ {d.avg_rating ?? 0}</b> <span className="text-ink-soft">({d.review_count ?? 0})</span></div>
            <Actions actions={d.actions} onTap={onTap} busy={busy} />
          </div>
        </Card>))}
    </div>)
  if (data.card === 'hospitals') return (
    <div className="grid md:grid-cols-2 gap-3 mt-2">
      {data.items.map(h => (
        <Card key={h.id} className="card-hover">
          <div className="font-bold">{h.name}</div>
          <div className="text-xs text-ink-soft">{h.city} · {h.doctor_count ?? 0} doctors · ★ {h.avg_rating ?? 0} ({h.review_count ?? 0})</div>
          <Actions actions={h.actions} onTap={onTap} busy={busy} />
        </Card>))}
    </div>)
  if (data.card === 'slots') return (
    <div className="grid sm:grid-cols-2 gap-2 mt-2">
      {data.items.map((s, i) => (
        <Card key={i} className="!p-3 card-hover">
          <div className="font-bold text-sm">📅 {new Date(s.starts_at).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</div>
          <div className="text-xs text-ink-soft">{new Date(s.ends_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })} · in person</div>
          <Actions actions={s.actions} onTap={onTap} busy={busy} />
        </Card>
      ))}
    </div>)
  if (data.card === 'appointment') {
    const a = data.items[0] || {}
    return (
      <Card className="border-brand/30 mt-2">
        <div className="flex flex-wrap items-center gap-2 text-sm">
          <b>Appointment #{a.appointment_id ?? a.id}</b>
          {a.status ? <Pill value={a.status} /> : null}
          {a.verified ? <span className="pill bg-emerald-50 text-emerald-700">✓ verified</span> : null}
        </div>
        {a.correlation_id ? <div className="mt-1 text-xs text-ink-faint">ref {a.correlation_id}</div> : null}
        <Actions actions={a.actions} onTap={onTap} busy={busy} />
      </Card>)
  }
  if (data.card === 'appointments') return (
    <Card className="mt-2">
      <div className="space-y-2">
        {data.items.map(a => (
          <div key={a.id} className="py-2 border-t border-slate-100 text-sm first:border-0 first:pt-0">
            <div className="flex justify-between gap-2"><span>{a.doctor_name} · {new Date(a.starts_at).toLocaleString()}</span><Pill value={a.status} /></div>
            <Actions actions={a.actions} onTap={onTap} busy={busy} />
          </div>))}
      </div>
    </Card>)
  if (data.card === 'reviews') return (
    <Card className="mt-2"><div className="font-bold text-sm">★ {data.avg ?? 0} ({data.count ?? 0} reviews)</div>
      {(data.items || []).map((r, i) => <div key={i} className="text-sm py-1.5 border-t border-slate-100">★ {r.rating} — {r.title || '(no title)'}</div>)}
    </Card>)
  if (data.card === 'questionnaires') return (
    <Card className="mt-2"><div className="font-bold text-sm">Pending questionnaires</div>
      {(data.items || []).map(q => <div key={q.response_id} className="py-1.5 border-t border-slate-100 text-sm"><span>{q.title} · {q.status}</span><Actions actions={q.actions} onTap={onTap} busy={busy} /></div>)}
      {!(data.items || []).length && <div className="text-sm text-ink-soft">None pending.</div>}
    </Card>)
  return null
}

export default function Assistant() {
  const [sp, setSp] = useSearchParams()
  const cid = sp.get('c')
  const [threads, setThreads] = useState([])
  const [msgs, setMsgs] = useState([])
  const [input, setInput] = useState('')
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')
  const bottom = useRef(null)
  const lastSent = useRef({ text: '', at: 0 })
  const loadSeq = useRef(0)
  // Voice v1: speak only voice-initiated replies (never surprise text users).
  const [muted, setMuted] = useState(() => localStorage.getItem('voice_muted') === '1')
  const expectVoiceReply = useRef(false)
  const ttsSupported = isTTSSupported()
  useEffect(() => { loadVoices().catch(() => {}) }, [])
  useEffect(() => () => stopSpeaking(), [])
  useEffect(() => { localStorage.setItem('voice_muted', muted ? '1' : '0'); if (muted) stopSpeaking() }, [muted])

  const loadThreads = () => api('/ai/conversations').then(setThreads).catch(() => {})
  const loadMsgs = (id) => {
    if (!id) { setMsgs([]); return }
    // Tool rows are internal trace — cards carry their data, so hide them.
    const seq = ++loadSeq.current
    api(`/ai/conversations/${id}/messages`).then(rs => {
      if (seq !== loadSeq.current) return // stale fetch — never clobber newer rows
      const server = (rs || []).filter(m => m.role !== 'tool')
      setMsgs(prev => {
        // Adopt server ids onto matching optimistic rows, keep in-flight last.
        const remaining = [...prev]
        const out = []
        for (const s of server) {
          const ti = remaining.findIndex(m => m.id == null && m.role === s.role && m.content === s.content)
          if (ti >= 0) {
            const [t] = remaining.splice(ti, 1)
            out.push({ ...t, id: s.id, created_at: s.created_at })
          } else out.push(s)
        }
        return [...out, ...remaining.filter(m => m.id == null)]
      })
    }).catch(() => {})
  }
  useEffect(() => { loadThreads() }, [])
  useEffect(() => { loadMsgs(cid) }, [cid])
  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [msgs, busy])

  const send = async (text, opts = {}) => {
    const body = (text ?? input).trim()
    if (!body || busy) return
    stopSpeaking() // barge-in: new turn cancels spoken reply
    if (opts.viaVoice) expectVoiceReply.current = true
    // Dedup impatient repeats: same text within 30s reuses the in-flight turn.
    const now = Date.now()
    if (lastSent.current.text === body && now - lastSent.current.at < 30000) {
      setErr('Already sent — waiting for the reply above.')
      return
    }
    lastSent.current = { text: body, at: now }
    loadSeq.current++ // invalidate any in-flight history fetch — send wins
    setBusy(true); setErr(''); setInput('')
    setMsgs(m => [...m, { role: 'user', content: body }])
    try {
      const r = await api('/ai/chat', { method: 'POST', timeout: 120000, body: { conversation_id: cid ? Number(cid) : null, message: body } })
      if (!cid && r.conversation_id) setSp({ c: String(r.conversation_id) })
      // Card + options ride on the message itself — one timeline, survives reload.
      setMsgs(m => [...m, { role: 'assistant', content: r.reply, data: r.data || {} }])
      if (expectVoiceReply.current && !muted && ttsSupported && r.reply) {
        expectVoiceReply.current = false
        speakReply(r.reply, { onerror: () => setErr('Voice playback failed — reply shown as text.') }).catch(() => {})
      } else expectVoiceReply.current = false
      loadThreads()
    } catch (e) {
      setErr(e.message)
    } finally { setBusy(false) }
  }

  return (
    <div className="-m-4 md:-m-7">
      <div className="grid md:grid-cols-[240px_1fr] gap-2 p-2 md:p-3">
        <Card className="!p-3 h-[calc(100dvh-66px)] md:h-[calc(100dvh-44px)] md:min-h-[540px] flex flex-col">
          <div className="px-1 pb-2">
            <div className="font-display text-[15px] font-semibold leading-tight">AI Assistant</div>
            <div className="text-[11px] text-ink-soft leading-snug">Admin help with real availability — verified before confirmed.</div>
          </div>
          <button type="button" onClick={() => { setSp({}); setMsgs([]) }} className="btn-primary text-sm w-full">+ New chat</button>
          <div className="mt-3 space-y-1.5 flex-1 overflow-y-auto chat-scroll pr-1">
            {threads.map(t => (
              <button key={t.id} type="button" onClick={() => setSp({ c: String(t.id) })}
                className={`w-full text-left rounded-xl px-3 py-2 text-sm ${String(t.id) === cid ? 'bg-brand-soft font-bold' : 'hover:bg-slate-50'}`}>
                <div className="truncate">{t.preview || 'New conversation'}</div>
              </button>))}
            {!threads.length && <Empty title="No chats yet" sub="Start below — history saves to your account." />}
          </div>
        </Card>
        <Card className="flex flex-col h-[calc(100dvh-66px)] md:h-[calc(100dvh-44px)] md:min-h-[540px] !rounded-none md:!rounded-2xl border-x-0 md:border-x">
          <div className="flex-1 space-y-3 overflow-y-auto chat-scroll pr-1">
            {!msgs.length && !busy && <Empty title="Ask anything admin" sub="e.g. I need a shoulder doctor this week." />}
            {msgs.map((m, i) => (
              <div key={m.id ?? `tmp-${i}`} className="space-y-1">
                <Bubble role={m.role} content={m.content} />
                {m.role === 'assistant' && m.data?.card && <Cards data={m.data} onTap={send} busy={busy} />}
                {m.role === 'assistant' && <Options options={m.data?.options} onTap={send} busy={busy} />}
              </div>
            ))}
            {busy && <TypingBubble />}
            {err && <Card className="border-crit/40"><div className="text-sm font-bold text-crit">{err.includes('503') || err.includes('unavailable') ? 'AI unavailable — add INCEPTION_API_KEY.' : err}</div><Link to="/app/book" className="btn-ghost text-xs mt-2 inline-block">Book manually →</Link></Card>}
            <div ref={bottom} />
          </div>
          <div className="mt-2 flex gap-2 items-center">
            <VoiceOrb onTranscript={(t) => send(t, { viaVoice: true })} onError={setErr} busy={busy} disabled={busy} />
            {ttsSupported && (
              <button type="button" onClick={() => setMuted(m => !m)} title={muted ? 'Unmute voice replies' : 'Mute voice replies'}
                className="btn-ghost text-sm !px-3" aria-label={muted ? 'Unmute' : 'Mute'}>{muted ? '🔇' : '🔊'}</button>
            )}
            <input className="input flex-1" placeholder="Type a message… or tap 🎙 to speak" value={input} onChange={e => setInput(e.target.value)} onKeyDown={e => e.key === 'Enter' && send()} disabled={busy} aria-label="Message" />
            <button type="button" disabled={busy || !input.trim()} onClick={() => send()} className="btn-primary text-sm">{busy ? '…' : 'Send'}</button>
          </div>
        </Card>
      </div>
    </div>
  )
}
