"""Modular voice layer: browser Web Speech by default; server stubs for pluggable providers."""
import os, base64
async def stt_transcribe(audio_b64: str = "", mime: str = "audio/webm", provider: str = "") -> dict:
    provider = provider or os.getenv("VOICE_STT_PROVIDER", "browser")
    key = os.getenv("VOICE_API_KEY", "")
    if provider == "browser" or not key:
        return {"provider": provider, "mode": "client", "hint": "Use browser Web Speech API for STT; send transcript to /ai/chat."}
    return {"provider": provider, "mode": "server", "transcript": ""}
async def tts_synthesize(text: str, voice: str = "alloy", provider: str = "") -> dict:
    provider = provider or os.getenv("VOICE_TTS_PROVIDER", "browser")
    key = os.getenv("VOICE_API_KEY", "")
    if provider == "browser" or not key:
        return {"provider": provider, "mode": "client", "hint": "Use browser speechSynthesis for TTS."}
    return {"provider": provider, "mode": "server", "audio_b64": base64.b64encode(f"tts:{text[:50]}".encode()).decode()}
