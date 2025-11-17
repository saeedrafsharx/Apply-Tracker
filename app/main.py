from __future__ import annotations
import os
from datetime import datetime, timezone
from typing import Optional

from fastapi import FastAPI, Request, Form, UploadFile, File
from fastapi.responses import RedirectResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.base import BaseHTTPMiddleware

from sqlalchemy import select, or_
from sqlalchemy.orm import Session

from .db import engine, session_scope
from .models import Base, User, Contact, Position
from .schemas import UserCreate, Login, ContactCreate
from .auth import get_password_hash, verify_password

SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-change-me")

app = FastAPI(title="ApplyList · Contact Tracker")

# Session middleware
app.add_middleware(SessionMiddleware, secret_key=SECRET_KEY, session_cookie="ct_session")


class UserLoaderMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        user = None
        if "session" in request.scope:
            uid = request.session.get("uid")
            if uid:
                with session_scope() as db:
                    user = db.get(User, int(uid))
        request.state.user = user
        return await call_next(request)


app.add_middleware(UserLoaderMiddleware)

# Static & templates
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


def current_user(request: Request, db: Session) -> Optional[User]:
    uid = request.session.get("uid")
    if not uid:
        return None
    return db.get(User, int(uid))


# ───────── startup / seed ─────────
@app.on_event("startup")
def on_startup() -> None:
    Base.metadata.create_all(bind=engine)
    with session_scope() as db:
        any_user = db.execute(select(User).limit(1)).scalar_one_or_none()
        if not any_user:
            demo = User(
                username="demo",
                email="demo@example.com",
                password_hash=get_password_hash("demo1234"),
            )
            db.add(demo)
            db.flush()
            seed = [
                dict(
                    name="Danilo Bzdok",
                    university="McGill (IPN)",
                    research_focus="computational neuroimaging, ML",
                    contact_email="danilo.bzdok@mcgill.ca",
                    source_url="https://www.mcgill.ca/ipn/prospective/supervisors-recruiting",
                    category="Professors",
                ),
                dict(
                    name="Boris Bernhardt",
                    university="McGill (IPN)",
                    research_focus="network analysis, neuroimaging",
                    contact_email="boris.bernhardt@mcgill.ca",
                    source_url="https://www.mcgill.ca/ipn/prospective/supervisors-recruiting",
                    category="Professors",
                ),
                dict(
                    name="Mahsa Dadar",
                    university="McGill (IPN)",
                    research_focus="brain imaging, aging, ML",
                    contact_email="mahsa.dadar@mcgill.ca",
                    source_url="https://www.mcgill.ca/ipn/prospective/supervisors-recruiting",
                    category="Professors",
                ),
            ]
            for it in seed:
                db.add(Contact(owner_id=demo.id, **it))


# ───────── basic routes ─────────
@app.get("/health")
def health():
    return {"status": "ok"}


# New home page with category buttons
@app.get("/")
def home(request: Request):
    return templates.TemplateResponse("home.html", {"request": request})


# Backwards-compat: /dashboard → /professors
@app.get("/dashboard")
def dashboard_redirect():
    return RedirectResponse("/professors", status_code=307)


@app.get("/login")
def login_form(request: Request):
    if request.state.user:
        return RedirectResponse("/professors", status_code=303)
    return templates.TemplateResponse("login.html", {"request": request})


@app.get("/register")
def register_form(request: Request):
    if request.state.user:
        return RedirectResponse("/professors", status_code=303)
    return templates.TemplateResponse("register.html", {"request": request})


@app.post("/login")
def login(request: Request, username: str = Form(...), password: str = Form(...)):
    payload = Login(username=username, password=password)
    with session_scope() as db:
        user = (
            db.execute(select(User).where(User.username == payload.username))
            .scalar_one_or_none()
        )
        if not user or not verify_password(payload.password, user.password_hash):
            return templates.TemplateResponse(
                "login.html",
                {"request": request, "error": "Invalid credentials"},
                status_code=401,
            )
        request.session["uid"] = user.id
    return RedirectResponse("/professors", status_code=303)


@app.post("/register")
def register(
    request: Request,
    username: str = Form(...),
    email: str = Form(""),
    password: str = Form(...),
):
    payload = UserCreate(username=username, email=(email or None), password=password)
    with session_scope() as db:
        exists = (
            db.execute(select(User).where(User.username == payload.username))
            .scalar_one_or_none()
        )
        if exists:
            return templates.TemplateResponse(
                "register.html",
                {"request": request, "error": "Username already exists"},
                status_code=400,
            )
        user = User(
            username=payload.username,
            email=payload.email,
            password_hash=get_password_hash(payload.password),
        )
        db.add(user)
        db.flush()
        request.session["uid"] = user.id
    return RedirectResponse("/professors", status_code=303)


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/login", status_code=303)


# ───────── PROFESSORS DASHBOARD (Contacts) ─────────
@app.get("/professors")
def professors(
    request: Request,
    q: str = "",
    sort: str = "name",
    category: str = "",
):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)

        base_stmt = select(Contact).where(Contact.owner_id == user.id)

        # categories list for filter dropdown
        categories = (
            db.execute(
                select(Contact.category)
                .where(Contact.owner_id == user.id)
                .distinct()
            )
            .scalars()
            .all()
        )
        categories = sorted(
            [c for c in {c or "General" for c in categories}]
        )

        stmt = base_stmt

        # search
        if q:
            q_like = f"%{q.lower()}%"
            stmt = stmt.where(
                or_(
                    Contact.name.ilike(q_like),
                    Contact.university.ilike(q_like),
                    Contact.research_focus.ilike(q_like),
                    Contact.contact_email.ilike(q_like),
                )
            )

        # category filter
        if category:
            stmt = stmt.where(Contact.category == category)

        # sorting
        if sort == "university":
            stmt = stmt.order_by(Contact.university, Contact.name)
        elif sort == "email":
            stmt = stmt.order_by(Contact.contact_email, Contact.name)
        elif sort == "category":
            stmt = stmt.order_by(Contact.category, Contact.name)
        else:
            stmt = stmt.order_by(Contact.name)

        contacts = db.execute(stmt).scalars().all()

        stats = {
            "total": len(contacts),
            "sent": sum(1 for c in contacts if c.email_sent),
            "reminders": sum(1 for c in contacts if c.reminder_sent),
        }

        return templates.TemplateResponse(
            "index.html",
            {
                "request": request,
                "contacts": contacts,
                "user": user,
                "stats": stats,
                "q": q,
                "sort": sort,
                "category": category,
                "categories": categories,
            },
        )


# Add professor contact
@app.post("/add")
def add_contact(
    request: Request,
    name: str = Form(...),
    university: str = Form(...),
    research_focus: str = Form(...),
    contact_email: str = Form(...),
    source_url: str = Form(""),
    category: str = Form(""),
):
    payload = ContactCreate(
        name=name,
        university=university,
        research_focus=research_focus,
        contact_email=contact_email,
        source_url=source_url or "#",
    )
    category_norm = category.strip() or "General"

    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        db.add(
            Contact(
                owner_id=user.id,
                category=category_norm,
                **payload.model_dump(),
            )
        )
    return RedirectResponse("/professors", status_code=303)


@app.get("/edit/{contact_id}")
def edit_form(request: Request, contact_id: int):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        c = db.get(Contact, contact_id)
        if not c or c.owner_id != user.id:
            return RedirectResponse("/professors", status_code=303)
        return templates.TemplateResponse(
            "edit.html", {"request": request, "c": c, "user": user}
        )


@app.post("/edit/{contact_id}")
def edit_contact(
    request: Request,
    contact_id: int,
    name: str = Form(...),
    university: str = Form(...),
    research_focus: str = Form(...),
    contact_email: str = Form(...),
    source_url: str = Form(""),
    category: str = Form(""),
    email_sent: Optional[str] = Form(None),
    reminder_sent: Optional[str] = Form(None),
):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        c = db.get(Contact, contact_id)
        if not c or c.owner_id != user.id:
            return RedirectResponse("/professors", status_code=303)

        c.name = name.strip()
        c.university = university.strip()
        c.research_focus = research_focus.strip()
        c.contact_email = contact_email.strip()
        c.source_url = (source_url.strip() or "#")
        c.category = (category.strip() or "General")

        new_email_sent = email_sent is not None
        if new_email_sent != c.email_sent:
            c.email_sent = new_email_sent
            c.email_sent_at = (
                datetime.now(timezone.utc) if new_email_sent else None
            )

        c.reminder_sent = reminder_sent is not None

    return RedirectResponse("/professors", status_code=303)


@app.post("/delete/{contact_id}")
def delete_contact(request: Request, contact_id: int):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        c = db.get(Contact, contact_id)
        if c and c.owner_id == user.id:
            db.delete(c)
    return RedirectResponse("/professors", status_code=303)


@app.post("/toggle-email/{contact_id}")
def toggle_email(request: Request, contact_id: int):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        c = db.get(Contact, contact_id)
        if c and c.owner_id == user.id:
            c.email_sent = not c.email_sent
            c.email_sent_at = (
                datetime.now(timezone.utc) if c.email_sent else None
            )
    return RedirectResponse("/professors", status_code=303)


@app.post("/toggle-reminder/{contact_id}")
def toggle_reminder(request: Request, contact_id: int):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        c = db.get(Contact, contact_id)
        if c and c.owner_id == user.id:
            c.reminder_sent = not c.reminder_sent
    return RedirectResponse("/professors", status_code=303)


# CSV export/import for professors
@app.get("/export.csv")
def export_csv(request: Request):
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

    import csv, io

    output = io.StringIO(newline="")
    writer = csv.writer(output)
    writer.writerow(
        [
            "Name",
            "University",
            "Research Focus",
            "Contact Email",
            "Source URL",
            "Category",
            "Email Sent",
            "Email Sent At (UTC)",
            "Reminder Sent",
        ]
    )
    for c in contacts:
        writer.writerow(
            [
                c.name,
                c.university,
                c.research_focus,
                c.contact_email,
                c.source_url or "",
                c.category or "",
                "Yes" if c.email_sent else "No",
                (c.email_sent_at.isoformat() if c.email_sent_at else ""),
                "Yes" if c.reminder_sent else "No",
            ]
        )

    data = output.getvalue().encode("utf-8-sig")
    output.close()

    filename = f"applylist-{datetime.now(timezone.utc).strftime('%Y%m%d-%H%M%S')}.csv"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(
        iter([data]),
        media_type="text/csv; charset=utf-8",
        headers=headers,
    )


@app.post("/import.csv")
async def import_csv(request: Request, file: UploadFile = File(...)):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)

    raw = await file.read()

    for enc in ("utf-8-sig", "utf-8", "iso-8859-1"):
        try:
            text = raw.decode(enc)
            break
        except UnicodeDecodeError:
            text = None
    if text is None:
        text = raw.decode("utf-8", "ignore")

    import csv, io
    from datetime import datetime as dt

    def norm(s: str) -> str:
        return "".join(ch.lower() for ch in (s or "") if ch.isalnum())

    aliases = {
        "name": ["name", "fullname", "contactname"],
        "university": ["university", "uni", "institution", "school"],
        "research_focus": [
            "researchfocus",
            "researcharea",
            "area",
            "topic",
            "field",
        ],
        "contact_email": [
            "contactemail",
            "email",
            "emailaddress",
            "e-mail",
            "mail",
        ],
        "source_url": [
            "sourceurl",
            "source",
            "link",
            "url",
            "website",
            "page",
        ],
        "category": ["category", "folder", "group"],
        "email_sent": ["emailsent", "sent", "emailsentflag"],
        "email_sent_at": [
            "emailsentat",
            "emailsentdate",
            "sentat",
            "emailsenton",
        ],
        "reminder_sent": ["remindersent", "reminder", "followup", "followupsent"],
    }

    candidates = [",", ";", "\t", "|"]
    picked = None
    header = []
    for delim in candidates:
        test = csv.reader(io.StringIO(text), delimiter=delim)
        header = next(test, [])
        normed = [norm(h) for h in header]
        known = sum(
            1
            for h in normed
            if any(h in [*vals] for vals in aliases.values())
        )
        if known >= 2:
            picked = delim
            break
    if not picked:
        picked = ","

    dict_reader = csv.DictReader(io.StringIO(text), delimiter=picked)
    header_row = dict_reader.fieldnames or []
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
        for fmt in (
            "%Y-%m-%dT%H:%M:%S%z",
            "%Y-%m-%dT%H:%M:%S",
            "%Y-%m-%d %H:%M",
            "%Y-%m-%d",
        ):
            try:
                if s.endswith("Z"):
                    s = s[:-1] + "+00:00"
                return dt.strptime(s, fmt)
            except Exception:
                continue
        try:
            return dt.fromisoformat(s)
        except Exception:
            return None

    created, updated, skipped = 0, 0, 0

    with session_scope() as db:
        user = current_user(request, db)
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
            category = (val(row, "category").strip() or "General")

            email_sent = to_bool(val(row, "email_sent"))
            email_sent_at = parse_dt(val(row, "email_sent_at"))
            reminder_sent = to_bool(val(row, "reminder_sent"))

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
                if university:
                    existing.university = university
                if research_focus:
                    existing.research_focus = research_focus
                if source_url:
                    existing.source_url = source_url
                if category:
                    existing.category = category
                existing.email_sent = email_sent
                existing.email_sent_at = (
                    email_sent_at if email_sent else None
                )
                existing.reminder_sent = reminder_sent
                updated += 1
            else:
                db.add(
                    Contact(
                        owner_id=user.id,
                        name=name,
                        university=university or "",
                        research_focus=research_focus or "",
                        contact_email=contact_email,
                        source_url=source_url,
                        category=category,
                        email_sent=email_sent,
                        email_sent_at=(
                            email_sent_at if email_sent else None
                        ),
                        reminder_sent=reminder_sent,
                    )
                )
                created += 1

    return RedirectResponse(
        f"/professors?imported={created}&updated={updated}&skipped={skipped}",
        status_code=303,
    )


# ───────── POSITIONS DASHBOARD ─────────
@app.get("/positions")
def positions(
    request: Request,
    q: str = "",
    sort: str = "field",
    category: str = "",
):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)

        base_stmt = select(Position).where(Position.owner_id == user.id)

        categories = (
            db.execute(
                select(Position.category)
                .where(Position.owner_id == user.id)
                .distinct()
            )
            .scalars()
            .all()
        )
        categories = sorted(
            [c for c in {c or "General" for c in categories}]
        )

        stmt = base_stmt

        if q:
            q_like = f"%{q.lower()}%"
            stmt = stmt.where(
                or_(
                    Position.field.ilike(q_like),
                    Position.link.ilike(q_like),
                )
            )

        if category:
            stmt = stmt.where(Position.category == category)

        if sort == "link":
            stmt = stmt.order_by(Position.link, Position.field)
        elif sort == "category":
            stmt = stmt.order_by(Position.category, Position.field)
        else:
            stmt = stmt.order_by(Position.field)

        positions = db.execute(stmt).scalars().all()

        stats = {
            "total": len(positions),
        }

        return templates.TemplateResponse(
            "positions.html",
            {
                "request": request,
                "positions": positions,
                "user": user,
                "stats": stats,
                "q": q,
                "sort": sort,
                "category": category,
                "categories": categories,
            },
        )


@app.post("/positions/add")
def add_position(
    request: Request,
    field: str = Form(...),
    link: str = Form(...),
    category: str = Form(""),
):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        db.add(
            Position(
                owner_id=user.id,
                field=field.strip(),
                link=link.strip(),
                category=(category.strip() or "General"),
            )
        )
    return RedirectResponse("/positions", status_code=303)


@app.get("/positions/edit/{position_id}")
def edit_position_form(request: Request, position_id: int):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        p = db.get(Position, position_id)
        if not p or p.owner_id != user.id:
            return RedirectResponse("/positions", status_code=303)
        return templates.TemplateResponse(
            "edit_position.html", {"request": request, "p": p, "user": user}
        )


@app.post("/positions/edit/{position_id}")
def edit_position(
    request: Request,
    position_id: int,
    field: str = Form(...),
    link: str = Form(...),
    category: str = Form(""),
):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        p = db.get(Position, position_id)
        if not p or p.owner_id != user.id:
            return RedirectResponse("/positions", status_code=303)

        p.field = field.strip()
        p.link = link.strip()
        p.category = category.strip() or "General"

    return RedirectResponse("/positions", status_code=303)


@app.post("/positions/delete/{position_id}")
def delete_position(request: Request, position_id: int):
    with session_scope() as db:
        user = current_user(request, db)
        if not user:
            return RedirectResponse("/login", status_code=303)
        p = db.get(Position, position_id)
        if p and p.owner_id == user.id:
            db.delete(p)
    return RedirectResponse("/positions", status_code=303)
