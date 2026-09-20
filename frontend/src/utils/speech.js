/* Browser TTS v1 — no model, no key, no download.
   Wraps speechSynthesis with the 3 prod fixes:
   1. wait for voiceschanged (else silent first tap)
   2. chunk >200 chars by sentence (Chrome cutoff)
   3. must be called in user gesture (orb tap) for Safari. */
import { plainForSpeech } from './markdown.js'

export function isTTSSupported() {
  return typeof window !== 'undefined' && 'speechSynthesis' in window
}

let voicesCache = null
export function loadVoices() {
  return new Promise((resolve) => {
    if (!isTTSSupported()) return resolve([])
    const synth = window.speechSynthesis
    const got = synth.getVoices()
    if (got && got.length) { voicesCache = got; return resolve(got) }
    const timer = setTimeout(() => { const v = synth.getVoices(); voicesCache = v; resolve(v || []) }, 1200)
    const onChange = () => {
      clearTimeout(timer)
      const v = synth.getVoices()
      voicesCache = v
      synth.removeEventListener?.('voiceschanged', onChange)
      resolve(v || [])
    }
    synth.addEventListener?.('voiceschanged', onChange)
  })
}

export function pickVoice(voices) {
  if (!voices?.length) return null
  const en = voices.filter((v) => /^en([-_]|$)/i.test(v.lang || ''))
  return en.find((v) => v.default) || en[0] || voices[0]
}

/* Split long replies into speakable chunks (~190 chars, sentence boundaries). */
export function chunkForSpeech(text, max = 190) {
  const clean = plainForSpeech(text).replace(/\s+/g, ' ').trim()
  if (!clean) return []
  if (clean.length <= max) return [clean]
  const sentences = clean.match(/[^.!?]+[.!?]+["']?|\S.+$/g) || [clean]
  const out = []
  let cur = ''
  for (const s of sentences) {
    const t = s.trim()
    if (!t) continue
    if ((cur + ' ' + t).trim().length <= max) { cur = (cur + ' ' + t).trim(); continue }
    if (cur) out.push(cur)
    if (t.length <= max) { cur = t }
    else { // hard-split very long sentence
      for (let i = 0; i < t.length; i += max) out.push(t.slice(i, i + max))
      cur = ''
    }
  }
  if (cur) out.push(cur)
  return out.filter(Boolean)
}

export function stopSpeaking() {
  try { if (isTTSSupported()) window.speechSynthesis.cancel() } catch { /* noop */ }
}

/* Speak markdown reply aloud. Returns {cancel}. Sequential chunks, one onend at finish. */
export async function speakReply(markdown, { rate = 1, onend, onerror } = {}) {
  if (!isTTSSupported()) { onerror?.(new Error('TTS not supported in this browser')); return { cancel: () => {} } }
  stopSpeaking()
  const chunks = chunkForSpeech(markdown)
  if (!chunks.length) { onend?.(); return { cancel: () => {} } }
  const voices = voicesCache || await loadVoices()
  const voice = pickVoice(voices)
  const synth = window.speechSynthesis
  let cancelled = false
  let idx = 0
  const cancel = () => { cancelled = true; try { synth.cancel() } catch { /* noop */ } }
  const next = () => {
    if (cancelled) return
    if (idx >= chunks.length) { onend?.(); return }
    const u = new SpeechSynthesisUtterance(chunks[idx])
    if (voice) u.voice = voice
    u.rate = rate
    u.onend = () => { idx += 1; next() }
    u.onerror = (e) => {
      if (cancelled) return
      // 'interrupted'/'canceled' happen on intentional stop — not errors.
      if (e?.error === 'interrupted' || e?.error === 'canceled') return
      onerror?.(new Error(`Speech failed (${e?.error || 'unknown'})`))
    }
    synth.speak(u)
  }
  next()
  return { cancel }
}
