import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from ..core.config import settings
url = os.getenv("DATABASE_URL", settings.DATABASE_URL)
engine = create_engine(url, pool_pre_ping=True, future=True)
SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
def get_db():
    db = SessionLocal()
    try: yield db
    finally: db.close()
