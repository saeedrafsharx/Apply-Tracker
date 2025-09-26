from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy.orm import Mapped, relationship


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    email: Optional[str] = None
    password_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # SQLAlchemy 2.x typed relationship (no target class arg)
    contacts: Mapped[list["Contact"]] = relationship(back_populates="owner")


class Contact(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    university: str
    research_focus: str
    contact_email: str
    source_url: str

    email_sent: bool = Field(default=False)
    email_sent_at: Optional[datetime] = None
    reminder_sent: bool = Field(default=False)

    owner_id: Optional[int] = Field(default=None, foreign_key="user.id")
    # Use Optional[...] for the relationship typing too (safe with 3.12)
    owner: Mapped[Optional["User"]] = relationship(back_populates="contacts")
