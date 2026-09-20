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
    class Config:
        env_file = ".env"
        extra = "ignore"

@lru_cache
def get_settings() -> Settings:
    return Settings()
settings = get_settings()
