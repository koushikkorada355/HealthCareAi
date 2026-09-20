from pydantic_settings import BaseSettings
from functools import lru_cache

class Settings(BaseSettings):
    DATABASE_URL: str = "postgresql+psycopg2://care:carepass@localhost:5432/careplatform"
    JWT_SECRET: str = "change-me-to-a-long-random-secret-min-32-chars"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRE_MINUTES: int = 1440
    MOCK_EHR_URL: str = "http://mock-ehr:8001"
    MOCK_EHR_API_KEY: str = "mock-ehr-dev-key"
    BACKEND_CORS_ORIGINS: str = "http://localhost:5173,http://localhost:3000"
    ENVIRONMENT: str = "development"
    SEED_ON_STARTUP: bool = True
    FAILURE_INJECTION_RATE: float = 0.0
    GROK_API_KEY: str = ""
    XAI_API_KEY: str = ""
    GROK_MODEL: str = "grok-3-mini"
    GROK_BASE_URL: str = "https://api.x.ai/v1"
    OPENAI_API_KEY: str = ""
    OPENAI_MODEL: str = "gpt-4o-mini"
    # Primary LLM: Inception Labs Mercury (user provides key in .env)
    INCEPTION_API_KEY: str = ""
    INCEPTION_BASE_URL: str = "https://api.inceptionlabs.ai/v1"
    INCEPTION_MODEL: str = "mercury-2.5"
    # Fallback LLM: gpt-oss-120b via Groq
    GROQ_API_KEY: str = ""
    GROQ_BASE_URL: str = "https://api.groq.com/openai/v1"
    GROQ_MODEL: str = "openai/gpt-oss-120b"
    LLM_TIMEOUT_S: int = 45
    LLM_MAX_HOPS: int = 5
    AI_SHORT_WINDOW: int = 5
    # Voice (Phase 1): Mercury stays primary brain. STT via Groq-hosted
    # whisper-large-v3-turbo (open weights, no local). TTS v1 = browser
    # speechSynthesis (no model/key). No telephone.
    STT_PROVIDER: str = "groq-whisper"
    STT_MODEL: str = "whisper-large-v3-turbo"
    STT_LANGUAGE: str = "en"
    TTS_PROVIDER: str = "browser"
    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache
def get_settings() -> Settings:
    return Settings()
settings = get_settings()
