# --- Temporary Py3.12 fix for SQLModel issubclass bug ---
import sqlmodel.main, typing
_orig = sqlmodel.main.get_sqlalchemy_type
def _patched_get_sqlalchemy_type(field):
    t = getattr(field, "type_", None)
    # Skip if it's not an actual class (e.g., UnionType, ForwardRef)
    if not isinstance(t, type):
        return None
    return _orig(field)
sqlmodel.main.get_sqlalchemy_type = _patched_get_sqlalchemy_type
# --------------------------------------------------------

# app/models.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import List

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, relationship


class User(SQLModel, table=True):
    # Explicit SQLAlchemy Column for every DB field to avoid Py3.12 inference bugs
    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True)
    )
    username: str = Field(
        sa_column=Column(String, nullable=False, index=True)
    )
    email: str | None = Field(
        default=None,
        sa_column=Column(String, nullable=True)
    )
    password_hash: str = Field(
        sa_column=Column(String, nullable=False)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )

    # Typed ORM relationship (not a column)
    contacts: Mapped[List["Contact"]] = relationship(back_populates="owner")


class Contact(SQLModel, table=True):
    id: int | None = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True)
    )
    name: str = Field(
        sa_column=Column(String, nullable=False)
    )
    university: str = Field(
        sa_column=Column(String, nullable=False)
    )
    research_focus: str = Field(
        sa_column=Column(String, nullable=False)
    )
    contact_email: str = Field(
        sa_column=Column(String, nullable=False)
    )
    source_url: str = Field(
        sa_column=Column(String, nullable=False)
    )

    email_sent: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False)
    )
    email_sent_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    reminder_sent: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False)
    )

    owner_id: int | None = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("user.id"), nullable=True)
    )
    owner: Mapped["User" | None] = relationship(back_populates="contacts")
