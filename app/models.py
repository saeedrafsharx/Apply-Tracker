from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field, Relationship
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey


class User(SQLModel, table=True):
    # Use Field(primary_key=True) alone (no sa_column here)
    id: Optional[int] = Field(default=None, primary_key=True)

    username: str = Field(index=True)
    email: Optional[str] = Field(default=None, sa_column=Column(String, nullable=True))
    password_hash: str
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False),
    )

    # SQLModel relationship helper
    contacts: list["Contact"] = Relationship(back_populates="owner")


class Contact(SQLModel, table=True):
    # Use Field(primary_key=True) alone (no sa_column here)
    id: Optional[int] = Field(default=None, primary_key=True)

    name: str
    university: str
    research_focus: str
    contact_email: str
    source_url: str

    email_sent: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))
    email_sent_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )
    reminder_sent: bool = Field(default=False, sa_column=Column(Boolean, nullable=False, default=False))

    owner_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("user.id"), nullable=True),
    )
    owner: Optional["User"] = Relationship(back_populates="contacts")
