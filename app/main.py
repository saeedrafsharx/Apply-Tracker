from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from sqlmodel import Session, select

from .db import engine, init_db
from .models import Contact, User
from .auth import get_password_hash, verify_password

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

app = FastAPI(title="Contact Tracker")
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, session_cookie="ct_session")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# ─────────────────────────────── Helpers ───────────────────────────────

def get_user_from_session(request: Request) -> Optional[User]:
    uid = request.session.get("uid")
    if not uid:
        return None
    with Session(engine) as session:
        return session.get(User, uid)

@app.middleware("http")
async def attach_user(request: Request, call_next):
    request.state.user = get_user_from_session(request)
    return await call_next(request)

# ─────────────────────────────── Seed data ─────────────────────────────
SEED_CONTACTS: List[dict] = [
    {"name": "Danilo Bzdok", "university": "McGill (IPN)", "research_focus": "computational neuroimaging, ML", "contact_email": "danilo.bzdok@mcgill.ca", "source_url": "https://www.mcgill.ca/ipn/prospective/supervisors-recruiting"},
    {"name": "Boris Bernhardt", "university": "McGill (IPN)", "research_focus": "network analysis, neuroimaging", "contact_email": "boris.bernhardt@mcgill.ca", "source_url": "https://www.mcgill.ca/ipn/prospective/supervisors-recruiting"},
    {"name": "Mahsa Dadar", "university": "McGill (IPN)", "research_focus": "brain imaging, aging, ML", "contact_email": "mahsa.dadar@mcgill.ca", "source_url": "https://www.mcgill.ca/ipn/prospective/supervisors-recruiting"},
]

@app.on_event("startup")
def on_startup() -> None:
    init_db()
    with Session(engine) as session:
        any_user = session.exec(select(User).limit(1)).first()
        if not any_user:
            demo = User(username="demo", email="demo@example.com", password_hash=get_password_hash("demo1234"))
            session.add(demo)
            session.commit()
            session.refresh(demo)
            for row in SEED_CONTACTS:
                session.add(Contact(**row, owner_id=demo.id))
            session.commit()

# ─────────────────────────────── Routes ────────────────────────────────
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

@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    with Session(engine) as session:
        user = session.exec(select(User).where(User.username == username)).first()
        if not user or not verify_password(password, user.password_hash):
            return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid credentials"}, status_code=401)
        request.session["uid"] = user.id
    return RedirectResponse("/dashboard", status_code=303)

@app.get("/register")
def register_form(request: Request):
    if request.state.user:
        return RedirectResponse("/dashboard", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request})

@app.post("/register")
def register(request: Request, username: str = Form(...), email: str = Form(""), password: str = Form(...)):
    with Session(engine) as session:
        exists = session.exec(select(User).where(User.username == username)).first()
        if exists:
            return templates.TemplateResponse("register.html", {"request": request, "error": "Username already exists"}, status_code=400)
        user = User(username=username.strip(), email=email.strip() or None, password_hash=get_password_hash(password))
        session.add(user)
        session.commit()
        session.refresh(user)
        request.session["uid"] = user.id
    return RedirectResponse("/dashboard", status_code=303)

@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)

@app.get("/dashboard")
def dashboard(request: Request):
    if not request.state.user:
        return RedirectResponse("/login", status_code=303)
    user = request.state.user
    with Session(engine) as session:
        contacts = session.exec(
            select(Contact).where(Contact.owner_id == user.id).order_by(Contact.university, Contact.name)
        ).all()
        total = len(contacts)
        sent = sum(1 for c in contacts if c.email_sent)
        reminders = sum(1 for c in contacts if c.reminder_sent)
    return templates.TemplateResponse("index.html", {"request": request, "contacts": contacts, "user": user, "stats": {"total": total, "sent": sent, "reminders": reminders}})

# ───────────── CRUD (require login) ─────────────
@app.post("/add")
def add_contact(request: Request,
    name: str = Form(...),
    university: str = Form(...),
    research_focus: str = Form(...),
    contact_email: str = Form(...),
    source_url: str = Form("")
):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=303)
    with Session(engine) as session:
        c = Contact(
            name=name.strip(),
            university=university.strip(),
            research_focus=research_focus.strip(),
            contact_email=contact_email.strip(),
            source_url=source_url.strip() or "#",
            owner_id=user.id,
        )
        session.add(c)
        session.commit()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.get("/edit/{contact_id}")
def edit_form(request: Request, contact_id: int):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=303)
    with Session(engine) as session:
        c = session.get(Contact, contact_id)
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
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=303)
    with Session(engine) as session:
        c = session.get(Contact, contact_id)
        if not c or c.owner_id != user.id:
            return RedirectResponse("/dashboard", status_code=303)
        c.name = name.strip()
        c.university = university.strip()
        c.research_focus = research_focus.strip()
        c.contact_email = contact_email.strip()
        c.source_url = source_url.strip() or "#"

        new_email_sent = email_sent is not None
        if new_email_sent != c.email_sent:
            c.email_sent = new_email_sent
            c.email_sent_at = datetime.now(timezone.utc) if new_email_sent else None

        c.reminder_sent = reminder_sent is not None

        session.add(c)
        session.commit()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/delete/{contact_id}")
def delete_contact(request: Request, contact_id: int):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=303)
    with Session(engine) as session:
        c = session.get(Contact, contact_id)
        if c and c.owner_id == user.id:
            session.delete(c)
            session.commit()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/toggle-email/{contact_id}")
def toggle_email(request: Request, contact_id: int):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=303)
    with Session(engine) as session:
        c = session.get(Contact, contact_id)
        if c and c.owner_id == user.id:
            new_state = not c.email_sent
            c.email_sent = new_state
            c.email_sent_at = datetime.now(timezone.utc) if new_state else None
            session.add(c)
            session.commit()
    return RedirectResponse(url="/dashboard", status_code=303)

@app.post("/toggle-reminder/{contact_id}")
def toggle_reminder(request: Request, contact_id: int):
    user = request.state.user
    if not user:
        return RedirectResponse("/login", status_code=303)
    with Session(engine) as session:
        c = session.get(Contact, contact_id)
        if c and c.owner_id == user.id:
            c.reminder_sent = not c.reminder_sent
            session.add(c)
            session.commit()
    return RedirectResponse(url="/dashboard", status_code=303)