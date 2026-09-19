import React, { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../../api/client.js'
import { Card, PageHead, Pill } from '../../components/ui.jsx'
import { renderSafe, plainForSpeech } from '../../utils/markdown.js'

const SUGGESTIONS = [
  'I need to see a doctor for shoulder pain this week',
  'Find me a cardiologist',
  'What are my upcoming appointments?',
]

export default function Voice() {
  const [turns, setTurns] = useState([
    { role: 'assistant', text: 'Hi! Tap the orb and speak — for example "shoulder pain this week". I will check real availability and read the options back to you.' },
  ])
  const [conv, setConv] = useState(null)
  const [listening, setListening] = useState(false)
  const [thinking, setThinking] = useState(false)
  const [speaking, setSpeaking] = useState(false)
  const [interim, setInterim] = useState('')
  const [voiceOn, setVoiceOn] = useState(true)
  const [rate, setRate] = useState(1)
  const [voices, setVoices] = useState([])
  const [voiceURI, setVoiceURI] = useState('')
  const [bookBusy, setBookBusy] = useState(null)
  const [pending, setPending] = useState(null) // {doc, slot, reason, mode} — details asked BEFORE booking
  const [supported] = useState(() => typeof window !== 'undefined' && !!(window.SpeechRecognition || window.webkitSpeechRecognition))
  const recRef = useRef(null)
  const bottom = useRef(null)

  useEffect(() => { bottom.current?.scrollIntoView({ behavior: 'smooth' }) }, [turns, thinking])

  /* ---- speech synthesis ---- */
  useEffect(() => {
    if (!('speechSynthesis' in window)) return
    const load = () => {
      const vs = speechSynthesis.getVoices().filter(v => v.lang?.startsWith('en'))
      setVoices(vs)
      if (!voiceURI && vs.length) {
        const pref = vs.find(v => /google us english|zira|samantha|female/i.test(v.name)) || vs[0]
        setVoiceURI(pref.voiceURI)
      }
    }
    load()
    speechSynthesis.onvoiceschanged = load
    return () => { speechSynthesis.onvoiceschanged = null }
  }, [])

  const stopSpeaking = () => { if ('speechSynthesis' in window) speechSynthesis.cancel(); setSpeaking(false) }

  const speak = (text) => {
    if (!voiceOn || !('speechSynthesis' in window)) return
    stopSpeaking()
    const clean = plainForSpeech(text).slice(0, 500)
    if (!clean.trim()) return
    const u = new SpeechSynthesisUtterance(clean)
    const v = voices.find(x => x.voiceURI === voiceURI)
    if (v) u.voice = v
    u.rate = rate
    u.onstart = () => setSpeaking(true)
    u.onend = () => setSpeaking(false)
    u.onerror = () => setSpeaking(false)
    speechSynthesis.speak(u)
  }

  /* ---- conversation ---- */
  const send = async (text) => {
    const t = String(text || '').trim()
    if (!t || thinking) return
    stopSpeaking()
    setTurns(m => [...m, { role: 'user', text: t }])
    setInterim(''); setThinking(true)
    try {
      const r = await api('/ai/chat', { method: 'POST', body: { message: t, conversation_id: conv, channel: 'voice' } })
      setConv(r.conversation_id)
      setTurns(m => [...m, { role: 'assistant', text: r.reply, data: r.data, corr: r.correlation_id }])
      speak(r.reply)
    } catch (e) {
      const msg = `Sorry — I could not reach the assistant: ${e.message}`
      setTurns(m => [...m, { role: 'assistant', text: msg }])
      speak(msg)
    } finally { setThinking(false) }
  }

  const book = async () => {
    const p = pending
    if (!p || !p.reason.trim()) return
    const key = `${p.slot.calendar_id}-${p.slot.starts_at}`
    setBookBusy(key)
    try {
      const me = await api('/auth/me')
      if (!me.patient_id) throw new Error('This login has no patient profile.')
      const r = await api('/appointments', { method: 'POST', body: { hospital_id: p.doc.hospital_id, doctor_id: p.doc.id, patient_id: me.patient_id, starts_at: p.slot.starts_at, ends_at: p.slot.ends_at, calendar_id: p.slot.calendar_id, mode: p.mode, reason: p.reason.trim(), idempotency_key: `voice-${me.id}-${p.doc.id}-${p.slot.starts_at}-${Date.now().toString(36)}` } })
      setPending(null)
      const msg = `Confirmed! Appointment #${r.appointment_id} is ${r.status} and verified. [Open appointment](/app/appointments/${r.appointment_id})`
      setTurns(m => [...m, { role: 'assistant', text: msg }])
      speak(`Confirmed! Appointment ${r.appointment_id} is verified.`)
    } catch (e) {
      const msg = `Booking failed safely, no duplicate created: ${e.message}`
      setTurns(m => [...m, { role: 'assistant', text: msg }])
      speak(msg)
    } finally { setBookBusy(null) }
  }

  const askDetails = (doc, slot) => {
    setPending({ doc, slot, reason: '', mode: 'in_person' })
    speak('Almost done. Please tell me the reason for your visit, then confirm the booking.')
  }

  /* ---- speech recognition ---- */
  const startListening = () => {
    const SR = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SR) return
    stopSpeaking()
    try { recRef.current?.stop() } catch { /* noop */ }
    const rec = new SR()
    rec.lang = 'en-US'; rec.interimResults = true; rec.maxAlternatives = 1
    rec.onresult = (e) => {
      const t = Array.from(e.results).map(r => r[0].transcript).join('')
      setInterim(t)
      if (e.results[e.results.length - 1].isFinal) { setListening(false); setInterim(''); send(t) }
    }
    rec.onerror = (e) => {
      setListening(false); setInterim('')
      if (e?.error === 'not-allowed') setTurns(m => [...m, { role: 'assistant', text: 'Microphone access was blocked. Please allow the microphone in your browser, then try again.' }])
    }
    rec.onend = () => setListening(false)
    recRef.current = rec
    try { rec.start(); setListening(true) } catch { setListening(false) }
  }

  const onOrb = () => {
    if (speaking) { startListening(); return } // barge-in: interrupt + listen
    if (thinking) return
    if (listening) { try { recRef.current?.stop() } catch { /* noop */ } setListening(false); return }
    startListening()
  }

  useEffect(() => () => { try { recRef.current?.stop() } catch { /* noop */ } stopSpeaking() }, [])

  const orbLabel = listening ? 'LISTENING — tap to stop' : thinking ? 'THINKING…' : speaking ? 'SPEAKING — tap to interrupt' : 'TAP TO SPEAK'
  const orbColor = listening ? 'bg-coral' : thinking ? 'bg-apricot' : speaking ? 'bg-brand-deep' : 'bg-brand'

  return (
    <div>
      {/* header */}
      <div className="hero-gradient relative overflow-hidden rounded-2xl p-6 text-white shadow-lift md:p-8">
        <div className="flex flex-wrap items-center gap-2"><span className="pill bg-white/15 text-white">live voice · verified booking</span></div>
        <h1 className="font-display mt-1 text-2xl font-semibold md:text-3xl">Voice assistant</h1>
        <p className="text-sm text-white/80">Speech → AI → real availability → verified booking → spoken reply.</p>
      </div>

      <div className="mt-4 grid gap-4 lg:grid-cols-3">
        {/* conversation */}
        <Card className="p-0 overflow-hidden lg:col-span-2">
          <div className="h-[46vh] overflow-auto p-4 space-y-3 bg-cream/60">
            {turns.map((m, i) => (
              <div key={i} className={`max-w-[88%] rounded-2xl px-4 py-2.5 text-sm ${m.role === 'user' ? 'ml-auto bg-brand text-white' : 'bg-white border border-slate-100 shadow-card'}`}>
                {m.role === 'assistant'
                  ? <div className="chatdoc whitespace-pre-wrap" dangerouslySetInnerHTML={{ __html: renderSafe(m.text) }} />
                  : <div className="whitespace-pre-wrap">{m.text}</div>}
                {m.corr && <div className="mt-1 text-[10px] opacity-60 font-mono">ref {m.corr}</div>}
                {m.data?.doctors && (
                  <div className="mt-2 space-y-2">
                    <div className="text-xs font-bold text-ink-soft">Tap a slot, then give details to book:</div>
                    {m.data.slots?.map(s => {
                      const key = `${s.calendar_id}-${s.starts_at}`
                      const isPending = pending?.slot.starts_at === s.starts_at && pending?.slot.calendar_id === s.calendar_id
                      return (
                      <div key={key} className="bg-cream rounded-xl px-3 py-2">
                        <div className="flex items-center justify-between">
                          <span className="font-semibold">{new Date(s.starts_at).toLocaleString([], { weekday: 'short', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
                          <button type="button" disabled={!!bookBusy} onClick={() => askDetails(m.data.doctors[0], s)} className="btn-primary text-xs !px-3 !py-1.5">{isPending ? '✓ Selected' : 'Select'}</button>
                        </div>
                        {isPending && (
                          <div className="mt-2 space-y-2 border-t border-brand/15 pt-2">
                            <input className="input !py-1.5 text-sm" placeholder="Reason for visit (required)…" aria-label="Reason for visit" value={pending.reason} onChange={e => setPending({ ...pending, reason: e.target.value })} />
                            <div className="flex gap-2">
                              <select className="input !py-1.5 text-sm" aria-label="Visit mode" value={pending.mode} onChange={e => setPending({ ...pending, mode: e.target.value })}>
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
            {thinking && <div className="flex items-center gap-1.5 text-sm text-ink-soft"><span className="dot" /><span className="dot" /><span className="dot" /> checking real availability…</div>}
            {interim && <div className="ml-auto max-w-[88%] rounded-2xl bg-brand/10 px-4 py-2.5 text-sm italic text-brand-ink">“{interim}…”</div>}
            <div ref={bottom} />
          </div>
          <div className="flex flex-wrap gap-2 border-t border-slate-100 bg-white p-3">
            {SUGGESTIONS.map(s => <button key={s} type="button" onClick={() => send(s)} disabled={thinking} className="btn-ghost text-xs">“{s}”</button>)}
          </div>
        </Card>

        {/* controls */}
        <div className="space-y-4">
          <Card className="text-center">
            <button type="button" onClick={onOrb} disabled={!supported || thinking}
              className={`orb mx-auto h-28 w-28 rounded-full font-bold text-white text-sm transition ${orbColor} ${!supported ? 'opacity-40' : ''}`}>
              {orbLabel}
            </button>
            {!supported && <p className="mt-3 text-sm text-ink-soft">Voice recognition is not supported in this browser. <Link to="/app/assistant" className="font-bold text-brand-deep underline">Use the text assistant instead →</Link></p>}
            <div className="mt-3 flex justify-center gap-2 text-xs">
              <span className="pill bg-slate-100 text-slate-600">barge-in: tap orb</span>
              <span className="pill bg-slate-100 text-slate-600">hands-free booking</span>
            </div>
          </Card>
          <Card>
            <div className="flex items-center justify-between">
              <div className="text-xs font-bold">VOICE REPLIES</div>
              <button type="button" onClick={() => { setVoiceOn(!voiceOn); if (voiceOn) stopSpeaking() }} className="btn-ghost text-xs !px-3 !py-1.5">{voiceOn ? 'On' : 'Off'}</button>
            </div>
            <label htmlFor="voice-pick" className="mt-3 block text-xs font-bold">VOICE</label>
            <select id="voice-pick" className="input mt-1 text-sm" value={voiceURI} onChange={e => setVoiceURI(e.target.value)}>
              {voices.map(v => <option key={v.voiceURI} value={v.voiceURI}>{v.name} · {v.lang}</option>)}
              {!voices.length && <option value="">System default</option>}
            </select>
            <label htmlFor="voice-rate" className="mt-3 block text-xs font-bold">SPEED · {rate.toFixed(1)}×</label>
            <input id="voice-rate" type="range" min="0.7" max="1.4" step="0.1" value={rate} onChange={e => setRate(Number(e.target.value))} className="mt-1 w-full" />
            {speaking && <button type="button" onClick={stopSpeaking} className="btn-ghost mt-3 w-full text-xs">Stop speaking</button>}
          </Card>
        </div>
      </div>
    </div>
  )
}
