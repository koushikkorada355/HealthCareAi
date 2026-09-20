import logging
import os
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .db.base import Base
from .db.session import engine
from .core.config import settings
from .api.v1 import auth, hospitals, doctors, scheduling, appointments, questionnaires, reviews, ops, notifications, workflows, ai, mcp

logger = logging.getLogger("careaccess")

@asynccontextmanager
async def lifespan(app: FastAPI):
    from . import models  # noqa: ensure registered
    Base.metadata.create_all(bind=engine)
    # Additive lightweight migrations (idempotent, never block boot).
    try:
        from sqlalchemy import text as _text
        with engine.begin() as _conn:
            _conn.execute(_text(
                "ALTER TABLE ai_messages ADD COLUMN IF NOT EXISTS "
                "data_json TEXT DEFAULT ''"))
    except Exception:
        logger.exception("light migration failed")
    # Option A concurrency guard: overlapping-range exclusion (Postgres/Neon only,
    # idempotent, skipped on SQLite). Never blocks boot on failure.
    try:
        from .db.exclusion import ensure_exclusion
        ensure_exclusion(engine)
    except Exception:
        logger.exception("exclusion constraint setup failed")
    if os.getenv("SEED_ON_STARTUP", str(settings.SEED_ON_STARTUP)).lower() in ("1", "true", "yes"):
        try:
            from .db.session import SessionLocal
            from .db.seed import run
            db = SessionLocal()
            try:
                run(db)
            finally:
                db.close()
        except Exception:
            logger.exception("seed failed")
    yield

app = FastAPI(title="MediConnect Platform", version="1.0.0", docs_url="/docs", openapi_url="/openapi.json", lifespan=lifespan)

origins = [o.strip() for o in settings.BACKEND_CORS_ORIGINS.split(",") if o.strip()]
app.add_middleware(CORSMiddleware, allow_origins=origins, allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

@app.get("/health")
def health():
    return {"ok": True, "service": "backend"}

for r in [auth.router, hospitals.router, doctors.router, scheduling.router, appointments.router, questionnaires.router, reviews.router, workflows.router, notifications.router, ops.router, ai.router, mcp.router]:
    app.include_router(r, prefix="/api/v1")
