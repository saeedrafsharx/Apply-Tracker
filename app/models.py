from __future__ import annotations
from datetime import datetime, timezone
from sqlmodel import SQLModel, Field, Relationship

class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(index=True)
    email: str | None = None
    password_hash: str
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    # SQLAlchemy 2.x compatible generics
    contacts: list["Contact"] = Relationship(back_populates="owner")

class Contact(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    university: str
    research_focus: str
    contact_email: str
    source_url: str

    email_sent: bool = Field(default=False)
    email_sent_at: datetime | None = None
    reminder_sent: bool = Field(default=False)

    owner_id: int | None = Field(default=None, foreign_key="user.id")
    owner: User | None = Relationship(back_populates="contacts")
