from fastapi import APIRouter, Depends
from ...core.deps import get_current_user
from ...voice.providers import stt_transcribe, tts_synthesize

router = APIRouter(tags=["voice"])

@router.post("/voice/stt")
async def stt(body: dict, u=Depends(get_current_user)):
    return await stt_transcribe(body.get("audio_b64",""), body.get("mime","audio/webm"), body.get("provider",""))

@router.post("/voice/tts")
async def tts(body: dict, u=Depends(get_current_user)):
    return await tts_synthesize(body.get("text",""), body.get("voice","alloy"), body.get("provider",""))

@router.get("/voice/config")
def cfg(u=Depends(get_current_user)):
    import os
    return {"stt_provider": os.getenv("VOICE_STT_PROVIDER","browser"), "tts_provider": os.getenv("VOICE_TTS_PROVIDER","browser"), "grok_model": os.getenv("GROK_MODEL","grok-3-mini"), "note": "Browser speech by default; set VOICE_API_KEY + providers to use server voice."}
