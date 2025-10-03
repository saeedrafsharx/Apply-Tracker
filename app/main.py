from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import StreamingResponse
from fastapi import UploadFile, File
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

@app.get("/export.csv")
def export_csv(request: Request):
    # Auth
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)

        contacts = (
            db.execute(
                select(Contact)
                .where(Contact.owner_id == user.id)
                .order_by(Contact.university, Contact.name)
            )
            .scalars()
            .all()
        )

    # Build CSV (add BOM so Excel opens it cleanly)
    import csv, io
    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow([
        "Name",
        "University",
        "Research Focus",
        "Contact Email",
        "Source URL",
        "Email Sent",
        "Email Sent At (UTC)",
        "Reminder Sent",
    ])
    for c in contacts:
        writer.writerow([
            c.name,
            c.university,
            c.research_focus,
            c.contact_email,
            c.source_url or "",
            "Yes" if c.email_sent else "No",
            (c.email_sent_at.isoformat() if c.email_sent_at else ""),
            "Yes" if c.reminder_sent else "No",
        ])
    data = output.getvalue().encode("utf-8-sig")
    output.close()

    filename = f"applylist-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([data]), media_type="text/csv; charset=utf-8", headers=headers)

@app.post("/import.csv")
async def import_csv(request: Request, file: UploadFile = File(...)):
    # Auth
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)

    # Read the uploaded file
    raw = await file.read()

    # Decode with fallbacks
    for enc in ("utf-8-sig", "utf-8", "iso-8859-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            text = None
    if text is None:
        text = raw.decode("utf-8", "ignore")

    import csv, io
    from datetime import datetime

    # Normalize header: lowercase + remove non-alphanum
    def norm(s: str) -> str:
        return "".join(ch.lower() for ch in (s or "") if ch.isalnum())

    # Accept common synonyms
    aliases = {
        "name": ["name", "fullname", "contactname"],
        "university": ["university", "uni", "institution", "school"],
        "research_focus": ["researchfocus", "researcharea", "area", "topic", "field"],
        "contact_email": ["contactemail", "email", "emailaddress", "e-mail", "mail"],
        "source_url": ["sourceurl", "source", "link", "url", "website", "page"],
        "email_sent": ["emailsent", "sent", "emailsentflag"],
        "email_sent_at": ["emailsentat", "emailsentdate", "sentat", "emailsenton"],
        "reminder_sent": ["remindersent", "reminder", "followup", "followupsent"],
    }

    # Try common delimiters until header has enough known fields
    candidates = [",", ";", "\t", "|"]
    picked = None
    header = []
    for delim in candidates:
        test = csv.reader(io.StringIO(text), delimiter=delim)
        header = next(test, [])
        normed = [norm(h) for h in header]
        known = sum(
            1 for h in normed
            if any(h in [*vals] for vals in aliases.values())
        )
        if known >= 2:
            picked = delim
            break
    if not picked:
        picked = ","  # default

    dict_reader = csv.DictReader(io.StringIO(text), delimiter=picked)
    header_row = dict_reader.fieldnames or []

    # Build a map: target_field -> actual header name in file
    # (choose the first alias that exists in the file)
    norm_headers = {norm(h): h for h in header_row}
    wanted = {}
    for target, syns in aliases.items():
        for s in syns:
            if s in norm_headers:
                wanted[target] = norm_headers[s]
                break

    def val(row, target_name, default=""):
        h = wanted.get(target_name)
        return (row.get(h, default) if h else default)

    def to_bool(v) -> bool:
        s = str(v or "").strip().lower()
        return s in {"1", "true", "yes", "y", "on"}

    def parse_dt(v):
        s = (v or "").strip()
        if not s:
            return None
        # Accept ISO & common simple formats
        for fmt in ("%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
            try:
                if s.endswith("Z"):
                    s = s[:-1] + "+00:00"
                return datetime.strptime(s, fmt)
            except Exception:
                continue
        try:
            return datetime.fromisoformat(s)
        except Exception:
            return None

    created, updated, skipped = 0, 0, 0

    with session_scope() as db:
        user = current_user(request, db)  # re-check inside session
        if not user:
            return RedirectResponse("/login", status_code=303)

        for row in dict_reader:
            name = (val(row, "name").strip())
            contact_email = (val(row, "contact_email").strip())
            if not (name and contact_email):
                skipped += 1
                continue

            university = val(row, "university").strip()
            research_focus = val(row, "research_focus").strip()
            source_url = (val(row, "source_url").strip() or "#")

            email_sent = to_bool(val(row, "email_sent"))
            email_sent_at = parse_dt(val(row, "email_sent_at"))
            reminder_sent = to_bool(val(row, "reminder_sent"))

            # Upsert by (name + contact_email) per user
            existing = (
                db.execute(
                    select(Contact).where(
                        Contact.owner_id == user.id,
                        Contact.name == name,
                        Contact.contact_email == contact_email,
                    )
                )
                .scalars()
                .first()
            )

            if existing:
                if university:      existing.university = university
                if research_focus:  existing.research_focus = research_focus
                if source_url:      existing.source_url = source_url
                existing.email_sent = email_sent
                existing.email_sent_at = (email_sent_at if email_sent else None)
                existing.reminder_sent = reminder_sent
                updated += 1
            else:
                db.add(Contact(
                    owner_id=user.id,
                    name=name,
                    university=university or "",
                    research_focus=research_focus or "",
                    contact_email=contact_email,
                    source_url=source_url,
                    email_sent=email_sent,
                    email_sent_at=(email_sent_at if email_sent else None),
                    reminder_sent=reminder_sent,
                ))
                created += 1

    return RedirectResponse(f"/dashboard?imported={created}&updated={updated}&skipped={skipped}", status_code=303)
