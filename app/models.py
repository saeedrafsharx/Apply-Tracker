from __future__ import annotations
from typing import Optional
from datetime import datetime
from sqlmodel import SQLModel, Field

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