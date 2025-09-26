from __future__ import annotations
import os
from pathlib import Path
from sqlmodel import SQLModel, create_engine

DB_OVERRIDE = os.getenv("CONTACT_DB")
if DB_OVERRIDE:
    DB_PATH = DB_OVERRIDE
else:
    DB_PATH = str(Path(__file__).resolve().parent.parent / "contact_tracker.db")

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

def init_db() -> None:
    SQLModel.metadata.create_all(engine)