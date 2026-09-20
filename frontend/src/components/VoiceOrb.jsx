/* VoiceOrb v1 — simple browser push-to-talk. No telephone, no local model.
   Mic → MediaRecorder (webm) → POST /api/v1/ai/stt (Groq whisper-turbo, hosted)
   → onTranscript(text). Silence auto-stop 2s, 60s max, tap again = stop (barge-in).
   TTS playback itself lives in utils/speech.js (speechSynthesis, no model). */
import React, { useEffect, useRef, useState } from 'react'
import { token } from '../api/client.js'

const BASE = (import.meta.env.VITE_API_URL || '').replace(/\/+$/, '')
const MAX_MS = 60000
const SILENCE_MS = 2000

export default function VoiceOrb({ onTranscript, onError, disabled }) {
  const [state, setState] = useState('idle') // idle | recording | uploading
  const [secs, setSecs] = useState(0)
  const recRef = useRef(null)
  const streamRef = useRef(null)
  const ctxRef = useRef(null)
  const timerRef = useRef(null)
  const silenceRef = useRef(null)
  const startRef = useRef(0)
  const stoppedRef = useRef(false)

  useEffect(() => () => cleanup(), [])

  const cleanup = () => {
    clearInterval(timerRef.current); clearTimeout(silenceRef.current)
    try { recRef.current?.stream?.getTracks()?.forEach((t) => t.stop()) } catch { /* noop */ }
    try { streamRef.current?.getTracks()?.forEach((t) => t.stop()) } catch { /* noop */ }
    try { ctxRef.current?.close?.() } catch { /* noop */ }
    recRef.current = null; streamRef.current = null; ctxRef.current = null
  }

  const stopTracks = () => {
    try { streamRef.current?.getTracks()?.forEach((t) => t.stop()) } catch { /* noop */ }
    try { ctxRef.current?.close?.() } catch { /* noop */ }
  }

  const upload = async (blob) => {
    setState('uploading')
    try {
      const fd = new FormData()
      fd.append('audio', blob, 'turn.webm')
      const ctrl = new AbortController()
      const timer = setTimeout(() => ctrl.abort(), 60000)
      const res = await fetch(`${BASE}/api/v1/ai/stt`, {
        method: 'POST',
        headers: token() ? { Authorization: `Bearer ${token()}` } : {},
        body: fd, signal: ctrl.signal,
      })
      clearTimeout(timer)
      const data = await res.json().catch(() => ({}))
      if (!res.ok) throw new Error(data.detail || `STT HTTP ${res.status}`)
      if (data.text) onTranscript?.(data.text)
      else onError?.('No speech detected — try again.')
    } catch (e) {
      onError?.(e.name === 'AbortError' ? 'Voice timed out — try again.' : (e.message || 'Voice failed'))
    } finally { setState('idle'); setSecs(0) }
  }

  const finish = (rec, chunks) => {
    if (stoppedRef.current) return
    stoppedRef.current = true
    clearInterval(timerRef.current); clearTimeout(silenceRef.current)
    stopTracks()
    try {
      rec.onstop = () => {
        const blob = new Blob(chunks, { type: rec.mimeType || 'audio/webm' })
        if (blob.size < 800) { setState('idle'); setSecs(0); onError?.('Too short — hold orb and speak.'); return }
        upload(blob)
      }
      rec.stop()
    } catch { setState('idle'); setSecs(0) }
  }

  const start = async () => {
    if (state !== 'idle' || disabled) return
    if (!navigator.mediaDevices?.getUserMedia) { onError?.('Mic not supported — type instead.'); return }
    // Stop any spoken reply first (barge-in feel).
    try { window.speechSynthesis?.cancel() } catch { /* noop */ }
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
      streamRef.current = stream
      const mime = MediaRecorder.isTypeSupported('audio/webm;codecs=opus') ? 'audio/webm;codecs=opus' : 'audio/webm'
      const rec = new MediaRecorder(stream, { mimeType: mime })
      recRef.current = rec
      const chunks = []
      stoppedRef.current = false
      rec.ondataavailable = (e) => { if (e.data?.size) chunks.push(e.data) }
      rec.onerror = () => { cleanup(); setState('idle'); onError?.('Recording failed — type instead.') }
      rec.start(250)
      setState('recording'); setSecs(0)
      startRef.current = Date.now()
      timerRef.current = setInterval(() => {
        const s = Math.floor((Date.now() - startRef.current) / 1000)
        setSecs(s)
        if (Date.now() - startRef.current >= MAX_MS) finish(rec, chunks)
      }, 500)
      // Silence auto-stop via analyser (2s below threshold).
      try {
        const AC = window.AudioContext || window.webkitAudioContext
        const ctx = new AC()
        ctxRef.current = ctx
        const src = ctx.createMediaStreamSource(stream)
        const analyser = ctx.createAnalyser()
        analyser.fftSize = 512
        src.connect(analyser)
        const buf = new Uint8Array(analyser.frequencyBinCount)
        let quietSince = Date.now()
        const tick = () => {
          if (stoppedRef.current) return
          analyser.getByteTimeDomainData(buf)
          let peak = 0
          for (let i = 0; i < buf.length; i++) peak = Math.max(peak, Math.abs(buf[i] - 128))
          if (peak > 12) quietSince = Date.now()
          else if (Date.now() - quietSince > SILENCE_MS && Date.now() - startRef.current > 1500) { finish(rec, chunks); return }
          silenceRef.current = setTimeout(tick, 200)
        }
        tick()
      } catch { /* analyser optional — timer/max still stop */ }
      rec._chunks = chunks
    } catch {
      setState('idle')
      onError?.('Mic blocked — allow microphone or type instead.')
    }
  }

  const toggle = () => {
    if (state === 'recording' && recRef.current) { finish(recRef.current, recRef.current._chunks || []); return }
    if (state === 'idle') start()
  }

  const busy = state !== 'idle'
  return (
    <button
      type="button" onClick={toggle} disabled={disabled || state === 'uploading'}
      aria-label={state === 'recording' ? `Stop recording (${secs}s)` : 'Tap to speak'}
      title={state === 'recording' ? 'Tap to stop' : 'Tap orb → speak → auto-stops on silence'}
      className={`relative grid place-items-center h-11 w-11 rounded-full text-white font-bold transition active:scale-95 disabled:opacity-50 ${state === 'recording' ? 'bg-crit orb' : 'bg-brand hover:bg-brand-deep'}`}
    >
      {state === 'uploading' ? '…' : state === 'recording' ? '■' : '🎙'}
      {state === 'recording' && (
        <span className="absolute -bottom-5 text-[10px] font-semibold text-crit whitespace-nowrap">{secs}s · tap to stop</span>
      )}
    </button>
  )
}
