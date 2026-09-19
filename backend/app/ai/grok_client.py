import os

def grok_configured() -> bool:
    """True when the user provided a GROK_API_KEY in .env (no key is ever exposed)."""
    return bool(os.getenv("GROK_API_KEY", "").strip())

def grok_model() -> str:
    return os.getenv("GROK_MODEL", "grok-3-mini")

async def grok_chat(messages: list[dict], model: str = "", max_tokens: int = 600) -> str | None:
    """Call Grok (OpenAI-compatible). Returns None if no key/failure -> caller falls back to rules."""
    if not grok_configured():
        return None
    try:
        from openai import AsyncOpenAI
        # tight timeout: voice turns must stay conversational even if Grok is slow
        client = AsyncOpenAI(api_key=os.getenv("GROK_API_KEY", "").strip(),
                             base_url=os.getenv("GROK_BASE_URL", "https://api.x.ai/v1"),
                             timeout=15.0)
        r = await client.chat.completions.create(model=model or grok_model(), messages=messages, max_tokens=max_tokens, temperature=0.2)
        text = (r.choices[0].message.content or "").strip()
        return text or None
    except Exception:
        return None
