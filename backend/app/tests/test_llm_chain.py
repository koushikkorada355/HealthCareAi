"""LLM chain: Muse Spark primary -> Mercury fallback -> gpt-oss fallback, fail-closed.

Uses monkeypatched clients (no network, no keys needed).
"""
import pytest

from app.ai_assistant.services import llm as llm_mod
from app.core.config import settings


class _FakeClient:
    def __init__(self, text=None, exc=None):
        self._text = text
        self._exc = exc

    async def ainvoke(self, messages):
        if self._exc:
            raise self._exc
        class R: pass
        r = R()
        r.content = self._text
        return r


def _patch_keys(monkeypatch, muse="k-muse", mercury="k-merc", gptoss="k-gpt"):
    monkeypatch.setattr(settings, "MUSE_SPARK_API_KEY", muse)
    monkeypatch.setattr(settings, "MUSE_SPARK_BASE_URL", "https://api.meta.ai/v1")
    monkeypatch.setattr(settings, "MUSE_SPARK_MODEL", "muse-spark-1.3-contributor")
    monkeypatch.setattr(settings, "INCEPTION_API_KEY", mercury)
    monkeypatch.setattr(settings, "GROQ_API_KEY", gptoss)


async def test_muse_primary_used_first(monkeypatch):
    _patch_keys(monkeypatch)
    calls = []

    def _fake_make(kind):
        calls.append(kind)
        return _FakeClient(text="muse says hi")

    monkeypatch.setattr(llm_mod, "_make_client", _fake_make)
    res = await llm_mod.generate([{"role": "user", "content": "hi"}])
    assert res.content == "muse says hi"
    assert res.powered_by == "muse-spark-1.3-contributor"
    assert calls == ["muse"]


async def test_mercury_fallback_when_muse_fails(monkeypatch):
    _patch_keys(monkeypatch)

    def _fake_make(kind):
        if kind == "muse":
            return _FakeClient(exc=RuntimeError("muse down"))
        return _FakeClient(text="mercury says hi")

    monkeypatch.setattr(llm_mod, "_make_client", _fake_make)
    res = await llm_mod.generate([{"role": "user", "content": "hi"}])
    assert res.content == "mercury says hi"
    assert res.powered_by == settings.INCEPTION_MODEL


async def test_gptoss_fallback_when_both_fail(monkeypatch):
    _patch_keys(monkeypatch)

    def _fake_make(kind):
        if kind in ("muse", "mercury"):
            return _FakeClient(exc=RuntimeError(f"{kind} down"))
        return _FakeClient(text="gptoss says hi")

    monkeypatch.setattr(llm_mod, "_make_client", _fake_make)
    res = await llm_mod.generate([{"role": "user", "content": "hi"}])
    assert res.content == "gptoss says hi"
    assert res.powered_by == settings.GROQ_MODEL


async def test_fail_closed_when_all_down(monkeypatch):
    _patch_keys(monkeypatch)
    monkeypatch.setattr(llm_mod, "_make_client",
                        lambda kind: _FakeClient(exc=RuntimeError("down")))
    with pytest.raises(llm_mod.AINotAvailable):
        await llm_mod.generate([{"role": "user", "content": "hi"}])


async def test_skips_tiers_without_keys(monkeypatch):
    _patch_keys(monkeypatch, muse="", mercury="")
    seen = []

    def _fake_make(kind):
        seen.append(kind)
        if kind in ("muse", "mercury"):
            return None
        return _FakeClient(text="gptoss only")

    monkeypatch.setattr(llm_mod, "_make_client", _fake_make)
    res = await llm_mod.generate([{"role": "user", "content": "hi"}])
    assert res.content == "gptoss only"


def test_status_reports_three_tiers(monkeypatch):
    _patch_keys(monkeypatch)
    st = llm_mod.llm_status()
    assert st["muse_configured"] is True
    assert st["mercury_configured"] is True
    assert st["gptoss_configured"] is True
    assert st["primary_model"] == "muse-spark-1.3-contributor"
