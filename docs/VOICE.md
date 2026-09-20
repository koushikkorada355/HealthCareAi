# Voice v1 — browser orb (no telephone, no local)

Mercury-2.5 stays primary brain. Voice adds STT + spoken replies around the
existing LangGraph chain, nothing in booking/verify changes.

## Flow
```
tap orb → MediaRecorder (webm) → POST /api/v1/ai/stt
  → Groq whisper-large-v3-turbo (MIT, hosted) → {text}
 → POST /api/v1/ai/chat (existing 11-node graph + 23 MCP tools)
  → {reply, data.card} → speechSynthesis.speak(plainForSpeech(reply)) + cards
```

## Config (.env)
```
GROQ_API_KEY=...            # STT + gpt-oss fallback brain (already present)
STT_PROVIDER=groq-whisper
STT_MODEL=whisper-large-v3-turbo
STT_LANGUAGE=en
TTS_PROVIDER=browser         # speechSynthesis, no model/key
```
Brain order unchanged: `mercury-2.5 → gpt-oss-120b` (fail-closed 503).
`GET /api/v1/ai/voice-config` reports `{stt_model, tts_provider, stt_configured}`.

## Free-tier limits (Groq, verified)
`whisper-large-v3-turbo`: RPM 20 / RPD 2000 / ASH 7200s / ASD 28800s.
429 → orb shows "rate limited — wait and retry". ~$0.04/hr audio after free.

## Prod fixes included
1. `voiceschanged` wait before first speak (else silent first tap).
2. Chunk replies >190 chars by sentence (Chrome cutoff).
3. Speak only voice-initiated replies + mute toggle (never surprise text users).
4. Barge-in: new tap/send calls `cancel()` first.
5. Silence auto-stop 2s, 60s max, <800-byte guard, mic-blocked + no-speech errors as text.
6. Privacy: backend logs bytes/ctype only, never audio or transcripts. PHI stays in DB-backed chat, not logs.

## Files
- `backend/app/api/v1/ai.py` → `POST /ai/stt`, `GET /ai/voice-config`
- `backend/app/core/config.py` → `STT_*/TTS_PROVIDER`
- `frontend/src/components/VoiceOrb.jsx` → orb + recorder + upload
- `frontend/src/utils/speech.js` → voices/chunk/speak
- `frontend/src/pages/patient/Assistant.jsx` → orb + mute + auto-speak

## v2 (documented, not built)
Swap 1 function `speakReply()` → `play(await POST /ai/tts)` for hosted
open-weights TTS (Replicate/Fal XTTS-v2). Keep browser TTS as offline fallback.
