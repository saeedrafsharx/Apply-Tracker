from __future__ import annotations
import os
from pathlib import Path
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

DB_OVERRIDE = os.getenv("CONTACT_DB")
if DB_OVERRIDE:
    DB_PATH = DB_OVERRIDE
else:
    DB_PATH = str(Path(__file__).resolve().parent.parent / "contact_tracker.db")

DATABASE_URL = f"sqlite:///{DB_PATH}"

engine = create_engine(
    DATABASE_URL,
    future=True,
    echo=False,
    pool_pre_ping=True,
)

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False, expire_on_commit=False, future=True)

# FastAPI dependency
from contextlib import contextmanager

@contextmanager
def session_scope():
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()