from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlalchemy import select
from sqlalchemy.orm import Session

from .db import engine, session_scope
from .models import Base, User, Contact
from .schemas import UserCreate, Login, ContactCreate
from .auth import get_password_hash, verify_password
from starlette.middleware.base import BaseHTTPMiddleware
from .db import session_scope
from .models import User

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

app = FastAPI(title="Contact Tracker")

# 1) Session middleware MUST be first
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, session_cookie="ct_session")

# 2) Our user loader runs inside SessionMiddleware
class UserLoaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user = None
        # Only touch the session if SessionMiddleware already put it in scope
        if "session" in request.scope:
            uid = request.session.get("uid")
            if uid:
                with session_scope() as db:
                    user = db.get(User, int(uid))
        request.state.user = user
        return await call_next(request)

app.add_middleware(UserLoaderMiddleware)

# (rest of your setup)
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def current_user(request: Request, db: Session) -> Optional[User]:
    uid = request.session.get("uid")
    if not uid:
        return None
    return db.get(User, int(uid))


# ─────────────── startup / seed ───────────────
@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    from sqlalchemy import func
    with session_scope() as db:
        any_user = db.execute(select(User).limit(1)).scalar_one_or_none()
        if not any_user:
            demo = User(username="demo", email="demo@example.com", password_hash=get_password_hash("demo1234"))
            db.add(demo)
            db.flush()
            seed = [
                dict(name="Danilo Bzdok", university="McGill (IPN)", research_focus="computational neuroimaging, ML", contact_email="danilo.bzdok@mcgill.ca", source_url="https://www.mcgill.ca/ipn/prospective/supervisors-recruiting"),
                dict(name="Boris Bernhardt", university="McGill (IPN)", research_focus="network analysis, neuroimaging", contact_email="boris.bernhardt@mcgill.ca", source_url="https://www.mcgill.ca/ipn/prospective/supervisors-recruiting"),
                dict(name="Mahsa Dadar", university="McGill (IPN)", research_focus="brain imaging, aging, ML", contact_email="mahsa.dadar@mcgill.ca", source_url="https://www.mcgill.ca/ipn/prospective/supervisors-recruiting"),
            ]
            for it in seed:
                db.add(Contact(owner_id=demo.id, **it))


# ─────────────── routes ───────────────
@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def root() -> RedirectResponse:
    return RedirectResponse("/dashboard")

@app.get("/login")
def login_form(request: Request):
    if request.state.user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})

@app.get("/register")
def register_form(request: Request):
    if request.state.user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    payload = Login(username=username, password=password)
    with session_scope() as db:
        user = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
        if not user or not verify_password(payload.password, user.password_hash):
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"}, status_code=401)
        request.session["uid"] = user.id
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/register")
def register(request: Request, username: str = Form(...), email: str = Form(""), password: str = Form(...)):
    payload = UserCreate(username=username, email=(email or None), password=password)
    with session_scope() as db:
        exists = db.execute(select(User).where(User.username == payload.username)).scalar_one_or_none()
        if exists:
            return templates.TemplateResponse("register.html", {"request": request, "error": "Username already exists"}, status_code=400)
        user = User(username=payload.username, email=payload.email, password_hash=get_password_hash(payload.password))
        db.add(user)
        db.flush()
        request.session["uid"] = user.id
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

# dashboard
@app.get("/dashboard")
def dashboard(request: Request):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        contacts = db.execute(
            select(Contact).where(Contact.owner_id == user.id).order_by(Contact.university, Contact.name)
        ).scalars().all()
        stats = {
            "total": len(contacts),
            "sent": sum(1 for c in contacts if c.email_sent),
            "reminders": sum(1 for c in contacts if c.reminder_sent),
        }
        return templates.TemplateResponse("index.html", {"request": request, "contacts": contacts, "user": user, "stats": stats})

# CRUD
@app.post("/add")
def add_contact(request: Request,
    name: str = Form(...),
    university: str = Form(...),
    research_focus: str = Form(...),
    contact_email: str = Form(...),
    source_url: str = Form("")
):
    payload = ContactCreate(
        name=name, university=university, research_focus=research_focus,
        contact_email=contact_email, source_url=source_url or "#",
    )
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        db.add(Contact(owner_id=user.id, **payload.model_dump()))
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/edit/{contact_id}")
def edit_form(request: Request, contact_id: int):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        c = db.get(Contact, contact_id)
        if not c or c.owner_id != user.id:
            return RedirectResponse("/dashboard", status_code=303)
        return templates.TemplateResponse("edit.html", {"request": request, "c": c, "user": user})

@app.post("/edit/{contact_id}")
def edit_contact(
    request: Request,
    contact_id: int,
    name: str = Form(...),
    university: str = Form(...),
    research_focus: str = Form(...),
    contact_email: str = Form(...),
    source_url: str = Form(""),
    email_sent: Optional[str] = Form(None),
    reminder_sent: Optional[str] = Form(None),
):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        c = db.get(Contact, contact_id)
        if not c or c.owner_id != user.id:
            return RedirectResponse("/dashboard", status_code=303)
        c.name = name.strip()
        c.university = university.strip()
        c.research_focus = research_focus.strip()
        c.contact_email = contact_email.strip()
        c.source_url = (source_url.strip() or "#")

        new_email_sent = email_sent is not None
        if new_email_sent != c.email_sent:
            c.email_sent = new_email_sent
            c.email_sent_at = datetime.now(timezone.utc) if new_email_sent else None

        c.reminder_sent = reminder_sent is not None

    return RedirectResponse("/dashboard", status_code=303)

@app.post("/delete/{contact_id}")
def delete_contact(request: Request, contact_id: int):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        c = db.get(Contact, contact_id)
        if c and c.owner_id == user.id:
            db.delete(c)
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/toggle-email/{contact_id}")
def toggle_email(request: Request, contact_id: int):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        c = db.get(Contact, contact_id)
        if c and c.owner_id == user.id:
            c.email_sent = not c.email_sent
            c.email_sent_at = datetime.now(timezone.utc) if c.email_sent else None
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/toggle-reminder/{contact_id}")
def toggle_reminder(request: Request, contact_id: int):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        c = db.get(Contact, contact_id)
        if c and c.owner_id == user.id:
            c.reminder_sent = not c.reminder_sent
    return RedirectResponse("/dashboard", status_code=303)