from __future__ import annotations
from datetime import datetime, timezone
from typing import List, Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from sqlmodel import Session, select

from .db import engine, init_db
from .models import Contact

app = FastAPI(title="Contact Tracker")
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

# Seed data (runs once if table is empty)
SEED: List[dict] = [
    {"name": "Danilo Bzdok", "university": "McGill (IPN)", "research_focus": "computational neuroimaging, ML", "contact_email": "danilo.bzdok@mcgill.ca", "source_url": "https://www.mcgill.ca/ipn/prospective/supervisors-recruiting"},
    {"name": "Boris Bernhardt", "university": "McGill (IPN)", "research_focus": "network analysis, neuroimaging", "contact_email": "boris.bernhardt@mcgill.ca", "source_url": "https://www.mcgill.ca/ipn/prospective/supervisors-recruiting"},
    {"name": "Mahsa Dadar", "university": "McGill (IPN)", "research_focus": "brain imaging, aging, ML", "contact_email": "mahsa.dadar@mcgill.ca", "source_url": "https://www.mcgill.ca/ipn/prospective/supervisors-recruiting"},
    {"name": "Yashar Zeighami", "university": "McGill (IPN)", "research_focus": "multiscale MRI, aging models", "contact_email": "yashar.zeighami@mcgill.ca", "source_url": "https://www.mcgill.ca/ipn/prospective/supervisors-recruiting"},
    {"name": "Yasser Iturria-Medina", "university": "McGill (IPN)", "research_focus": "computational modeling, neurodegeneration", "contact_email": "yasser.iturriamedina@mcgill.ca", "source_url": "https://www.mcgill.ca/ipn/prospective/supervisors-recruiting"},
    {"name": "David Rudko", "university": "McGill (IPN)", "research_focus": "ultra-high-field MRI methods", "contact_email": "david.rudko@mcgill.ca", "source_url": "https://www.mcgill.ca/ipn/prospective/supervisors-recruiting"},
    {"name": "Alain Ptito", "university": "McGill (IPN)", "research_focus": "fMRI, TBI/concussion", "contact_email": "alain.ptito@mcgill.ca", "source_url": "https://www.mcgill.ca/ipn/prospective/supervisors-recruiting"},
    {"name": "Pablo Rusjan", "university": "McGill (IPN)", "research_focus": "PET quantification", "contact_email": "pablo.rusjan@mcgill.ca", "source_url": "https://www.mcgill.ca/ipn/prospective/supervisors-recruiting"},
    {"name": "Gunnar Blohm", "university": "Queen’s (CNS)", "research_focus": "computational sensorimotor control", "contact_email": "gunnar.blohm@queensu.ca", "source_url": "https://neuroscience.queensu.ca/research/faculty"},
    {"name": "Jason Gallivan", "university": "Queen’s (CNS)", "research_focus": "fMRI, action, computation", "contact_email": "gallivan@queensu.ca", "source_url": "https://neuroscience.queensu.ca/profiles/faculty/jason-gallivan-58"},
    {"name": "Randy Flanagan", "university": "Queen’s (CNS)", "research_focus": "computational motor control", "contact_email": "flanagan@queensu.ca", "source_url": "https://neuroscience.queensu.ca/profiles/faculty/randy-flanagan-55"},
    {"name": "Jordan Poppenk", "university": "Queen’s (CNS)", "research_focus": "fMRI, memory, modeling", "contact_email": "jpoppenk@queensu.ca", "source_url": "https://neuroscience.queensu.ca/profiles/faculty/jordan-poppenk-84"},
    {"name": "Martin Paré", "university": "Queen’s (CNS)", "research_focus": "cognitive & active vision", "contact_email": "martin.pare@queensu.ca", "source_url": "https://neuroscience.queensu.ca/profiles/faculty/martin-pare-174"},
]

@app.on_event("startup")
def on_startup() -> None:
    init_db()
    with Session(engine) as session:
        # Only seed if table is empty
        any_row = session.exec(select(Contact).limit(1)).first()
        if not any_row:
            for row in SEED:
                session.add(Contact(**row))
            session.commit()

@app.get("/health")
def health():
    return {"status": "ok"}

@app.get("/")
def index(request: Request):
    with Session(engine) as session:
        contacts = session.exec(select(Contact).order_by(Contact.university, Contact.name)).all()
    return templates.TemplateResponse("index.html", {"request": request, "contacts": contacts})

@app.post("/add")
def add_contact(
    name: str = Form(...),
    university: str = Form(...),
    research_focus: str = Form(...),
    contact_email: str = Form(...),
    source_url: str = Form(""),
):
    with Session(engine) as session:
        c = Contact(
            name=name.strip(),
            university=university.strip(),
            research_focus=research_focus.strip(),
            contact_email=contact_email.strip(),
            source_url=source_url.strip() or "#",
        )
        session.add(c)
        session.commit()
    return RedirectResponse(url="/", status_code=303)

@app.get("/edit/{contact_id}")
def edit_form(request: Request, contact_id: int):
    with Session(engine) as session:
        c = session.get(Contact, contact_id)
        if not c:
            return RedirectResponse("/", status_code=303)
    return templates.TemplateResponse("edit.html", {"request": request, "c": c})

@app.post("/edit/{contact_id}")
def edit_contact(
    contact_id: int,
    name: str = Form(...),
    university: str = Form(...),
    research_focus: str = Form(...),
    contact_email: str = Form(...),
    source_url: str = Form(""),
    email_sent: Optional[str] = Form(None),
    reminder_sent: Optional[str] = Form(None),
):
    with Session(engine) as session:
        c = session.get(Contact, contact_id)
        if c:
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
    return RedirectResponse(url="/", status_code=303)

@app.post("/delete/{contact_id}")
def delete_contact(contact_id: int):
    with Session(engine) as session:
        c = session.get(Contact, contact_id)
        if c:
            session.delete(c)
            session.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/toggle-email/{contact_id}")
def toggle_email(contact_id: int):
    with Session(engine) as session:
        c = session.get(Contact, contact_id)
        if c:
            new_state = not c.email_sent
            c.email_sent = new_state
            c.email_sent_at = datetime.now(timezone.utc) if new_state else None
            session.add(c)
            session.commit()
    return RedirectResponse(url="/", status_code=303)

@app.post("/toggle-reminder/{contact_id}")
def toggle_reminder(contact_id: int):
    with Session(engine) as session:
        c = session.get(Contact, contact_id)
        if c:
            c.reminder_sent = not c.reminder_sent
            session.add(c)
            session.commit()
    return RedirectResponse(url="/", status_code=303)