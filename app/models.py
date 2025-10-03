from __future__ import annotations
from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import String, DateTime, Boolean, ForeignKey, UniqueConstraint
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


class User(Base):
    __tablename__ = "user"
    __table_args__ = (
        UniqueConstraint("username", name="uq_user_username"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    contacts: Mapped[list["Contact"]] = relationship(back_populates="owner", cascade="all, delete-orphan")


class Contact(Base):
    __tablename__ = "contact"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    university: Mapped[str] = mapped_column(String(200), nullable=False)
    research_focus: Mapped[str] = mapped_column(String(500), nullable=False)
    contact_email: Mapped[str] = mapped_column(String(320), nullable=False)
    source_url: Mapped[str] = mapped_column(String(500), nullable=False, default="#")

    email_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    reminder_sent: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"))
    owner: Mapped[User] = relationship(back_populates="contacts")