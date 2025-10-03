from __future__ import annotations
from datetime import datetime
from typing import Optional
from pydantic import BaseModel, EmailStr


class UserCreate(BaseModel):
    username: str
    email: Optional[EmailStr] = None
    password: str

    model_config = dict(str_strip_whitespace=True)


class Login(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    email: Optional[EmailStr] = None

    model_config = dict(from_attributes=True)


class ContactBase(BaseModel):
    name: str
    university: str
    research_focus: str
    contact_email: EmailStr
    source_url: Optional[str] = "#"


class ContactCreate(ContactBase):
    pass


class ContactUpdate(ContactBase):
    email_sent: Optional[bool] = None
    reminder_sent: Optional[bool] = None


class ContactOut(ContactBase):
    id: int
    email_sent: bool
    email_sent_at: Optional[datetime] = None
    reminder_sent: bool

    model_config = dict(from_attributes=True)