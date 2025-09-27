# app/models.py
from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from sqlmodel import SQLModel, Field
from sqlalchemy import Column, Integer, String, DateTime, Boolean, ForeignKey
from sqlalchemy.orm import Mapped, relationship


class User(SQLModel, table=True):
    # Use explicit SQLAlchemy Column for every DB field to avoid type inference bugs on py3.12
    id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, primary_key=True)
    )
    username: str = Field(
        sa_column=Column(String, nullable=False, index=True)
    )
    email: Optional[str] = Field(
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

    # Typed ORM relationships (no positional target; type comes from Mapped[...])
    contacts: Mapped[list["Contact"]] = relationship(back_populates="owner")


class Contact(SQLModel, table=True):
    id: Optional[int] = Field(
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
    email_sent_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    reminder_sent: bool = Field(
        default=False,
        sa_column=Column(Boolean, nullable=False, default=False)
    )

    owner_id: Optional[int] = Field(
        default=None,
        sa_column=Column(Integer, ForeignKey("user.id"), nullable=True)
    )
    owner: Mapped[Optional["User"]] = relationship(back_populates="contacts")
