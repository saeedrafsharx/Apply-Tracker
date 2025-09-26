from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy.orm import relationship


class User(SQLModel, table=True):
    id: Optional[int] = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    email: Optional[str] = None
    password_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # Classic SQLAlchemy relationship with explicit target
    contacts: list["Contact"] = relationship("Contact", back_populates="owner")


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
    # Relationship back to User
    owner: Optional["User"] = relationship("User", back_populates="contacts")
