"""Voice v1 tests — Mercury stays primary; STT proxy validation (no network)."""
import io
import pytest
from starlette.datastructures import UploadFile as StarletteUploadFile


def _user(role="patient"):
    class U:
        pass
    u = U()
    u.role = role
    return u


def _upload(data: bytes, filename="turn.webm", ctype="audio/webm"):
    f = StarletteUploadFile(filename=filename, file=io.BytesIO(data))
    # starlette UploadFile in this version exposes .file; ensure attrs used by endpoint exist
    return f


def test_voice_config_defaults_mercury_primary():
    from app.core.config import settings

    assert settings.STT_PROVIDER == "groq-whisper"
    assert settings.STT_MODEL == "whisper-large-v3-turbo"
    assert settings.TTS_PROVIDER == "browser"
    assert settings.INCEPTION_MODEL == "mercury-2.5"  # untouched


def test_stt_routes_registered():
    from app.api.v1.ai import router

    paths = {(r.path, tuple(sorted(r.methods))) for r in router.routes}
    assert ("/ai/stt", ("POST",)) in paths
    assert ("/ai/voice-config", ("GET",)) in paths


async def test_stt_missing_key_503(monkeypatch):
    from fastapi import HTTPException
    from app.api.v1 import ai as ai_mod
    from app.core.config import settings

    monkeypatch.setattr(settings, "GROQ_API_KEY", "")
    with pytest.raises(HTTPException) as ei:
        await ai_mod.speech_to_text(audio=_upload(b"fake-audio-bytes"), u=_user())
    assert ei.value.status_code == 503


async def test_stt_empty_audio_400(monkeypatch):
    from fastapi import HTTPException
    from app.api.v1 import ai as ai_mod
    from app.core.config import settings

    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")
    with pytest.raises(HTTPException) as ei:
        await ai_mod.speech_to_text(audio=_upload(b""), u=_user())
    assert ei.value.status_code == 400


async def test_stt_forbidden_role(monkeypatch):
    from fastapi import HTTPException
    from app.api.v1 import ai as ai_mod

    with pytest.raises(HTTPException) as ei:
        await ai_mod.speech_to_text(audio=_upload(b"x"), u=_user(role="visitor"))
    assert ei.value.status_code == 403


async def test_stt_success_mocked(monkeypatch):
    from app.api.v1 import ai as ai_mod
    from app.core.config import settings

    monkeypatch.setattr(settings, "GROQ_API_KEY", "test-key")

    class FakeResp:
        status_code = 200

        def json(self):
            return {"text": "I need a shoulder doctor this week"}

    class FakeClient:
        def __init__(self, *a, **k):
            pass

        async def __aenter__(self):
            return self

        async def __aexit__(self, *a):
            return False

        async def post(self, *a, **k):
            return FakeResp()

    import httpx
    monkeypatch.setattr(httpx, "AsyncClient", FakeClient)
    out = await ai_mod.speech_to_text(audio=_upload(b"fake-audio"), u=_user())
    assert out["text"].startswith("I need a shoulder doctor")
    assert out["model"] == settings.STT_MODEL
