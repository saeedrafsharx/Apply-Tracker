# FastAPI + Jinja + Tailwind – Contact Tracker (RGB Edition)

This fixes the **Unexpected token (33:0) in /index.tsx** issue by keeping everything as a plain FastAPI project with **Jinja2 `.html` templates** only. If you previously placed these files inside a React/Next.js app, that bundler tried to parse Jinja syntax as TSX which caused the error. Please keep this project **separate** from any React/Next code and ensure template files end with `.html`.

> Quick question for you
>
> Are you trying to run this inside a React/Next.js project? If yes, the build system will parse Jinja templates as TSX and break. The code below is a standalone FastAPI app.

---

## File tree
```
contact-tracker/
├─ requirements.txt
├─ app/
│  ├─ main.py
│  ├─ db.py
│  └─ models.py
├─ templates/
│  ├─ base.html
│  ├─ index.html
│  └─ edit.html
├─ static/
│  └─ app.css        # optional, Tailwind via CDN is included
└─ tests/
   └─ test_app.py    # new tests
```

## Setup & run
```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```
Open http://127.0.0.1:8000

To run tests
```bash
pytest -q
```

> Tip
>
> You can override the SQLite path with `CONTACT_DB=/path/to/file.db` env var. Tests use a temp DB automatically.

---

## requirements.txt
```txt
fastapi>=0.111,<1.0
starlette>=0.39
uvicorn[standard]>=0.29
jinja2>=3.1
sqlmodel>=0.0.21
pydantic>=2.5
python-multipart>=0.0.9
# test deps
pytest>=8.0
httpx>=0.27
```

---

## app/db.py
```python
from __future__ import annotations
import os
from pathlib import Path
from sqlmodel import SQLModel, create_engine

# Allow tests or users to override DB location via CONTACT_DB
DB_OVERRIDE = os.getenv("CONTACT_DB")
if DB_OVERRIDE:
    DB_PATH = DB_OVERRIDE
else:
    DB_PATH = str(Path(__file__).resolve().parent.parent / "contact_tracker.db")

engine = create_engine(f"sqlite:///{DB_PATH}", echo=False)

def init_db() -> None:
    SQLModel.metadata.create_all(engine)
```

---

## app/models.py
```python
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
```

---

## app/main.py
```python
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
```

---

## templates/base.html
```html
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Contact Tracker</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <style>
      .gradient-card { position: relative; }
      .gradient-card::before {
        content: ""; position: absolute; inset: 0; padding: 1px; border-radius: 1rem;
        background: linear-gradient(135deg, #06b6d4, #8b5cf6, #10b981);
        -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
        -webkit-mask-composite: xor; mask-composite: exclude;
      }
    </style>
  </head>
  <body class="min-h-screen bg-gradient-to-br from-slate-50 via-white to-slate-100 text-slate-900">
    <header class="sticky top-0 z-10 bg-white/70 backdrop-blur border-b">
      <div class="max-w-7xl mx-auto px-4 py-4 flex items-center justify-between">
        <h1 class="text-xl font-semibold tracking-tight bg-clip-text text-transparent bg-gradient-to-r from-fuchsia-600 via-sky-600 to-emerald-600">Contact Tracker</h1>
        <a href="/" class="text-sm text-slate-600 hover:text-slate-900">Home</a>
      </div>
    </header>
    <main class="max-w-7xl mx-auto px-4 py-8">
      {% block content %}{% endblock %}
    </main>
    <footer class="max-w-7xl mx-auto px-4 py-10 text-xs text-slate-500">
      Built with FastAPI + Jinja + Tailwind · Colorful RGB theme ✨
    </footer>
  </body>
</html>
```

---

## templates/index.html
```html
{% extends "base.html" %}
{% block content %}
  <div class="grid gap-8">
    <!-- Add form -->
    <section class="relative gradient-card rounded-2xl bg-white shadow p-5">
      <h2 class="text-lg font-semibold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-sky-600 via-fuchsia-600 to-emerald-600">Add a contact</h2>
      <form action="/add" method="post" class="grid md:grid-cols-5 gap-3">
        <input name="name" required placeholder="Name" class="px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 focus:ring-sky-400" />
        <input name="university" required placeholder="University" class="px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 focus:ring-fuchsia-400" />
        <input name="research_focus" required placeholder="Research Focus" class="px-3 py-2 rounded-lg border md:col-span-2 focus:outline-none focus:ring-2 focus:ring-emerald-400" />
        <input name="contact_email" required type="email" placeholder="Contact Email" class="px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 focus:ring-sky-400" />
        <input name="source_url" placeholder="Source URL" class="px-3 py-2 rounded-lg border md:col-span-4 focus:outline-none focus:ring-2 focus:ring-fuchsia-400" />
        <div class="md:col-span-5">
          <button class="inline-flex items-center gap-2 px-4 py-2 rounded-xl bg-gradient-to-r from-sky-600 via-fuchsia-600 to-emerald-600 text-white shadow hover:opacity-95 active:opacity-90">Save</button>
        </div>
      </form>
    </section>

    <!-- List -->
    <section class="relative gradient-card rounded-2xl bg-white shadow overflow-hidden">
      <div class="px-5 py-4 border-b flex items-center justify-between">
        <h2 class="text-lg font-semibold bg-clip-text text-transparent bg-gradient-to-r from-emerald-600 via-sky-600 to-fuchsia-600">Contacts</h2>
        <p class="text-xs text-slate-500">Toggle statuses, edit or delete entries.</p>
      </div>

      <div class="overflow-x-auto">
        <table class="min-w-full text-sm">
          <thead>
            <tr class="bg-gradient-to-r from-slate-100 via-slate-50 to-slate-100 text-slate-700 text-left">
              <th class="px-4 py-3">Name</th>
              <th class="px-4 py-3">University</th>
              <th class="px-4 py-3">Research Focus</th>
              <th class="px-4 py-3">Email</th>
              <th class="px-4 py-3">Source</th>
              <th class="px-4 py-3">Email Sent</th>
              <th class="px-4 py-3">Sent At</th>
              <th class="px-4 py-3">Reminder</th>
              <th class="px-4 py-3">Actions</th>
            </tr>
          </thead>
          <tbody class="divide-y">
            {% for c in contacts %}
            <tr class="hover:bg-slate-50/70">
              <td class="px-4 py-3 font-medium flex items-center gap-2">
                <span class="inline-block h-2.5 w-2.5 rounded-full bg-gradient-to-r from-sky-500 via-fuchsia-500 to-emerald-500"></span>
                {{ c.name }}
              </td>
              <td class="px-4 py-3">{{ c.university }}</td>
              <td class="px-4 py-3 text-slate-700">{{ c.research_focus }}</td>
              <td class="px-4 py-3">
                <a class="text-sky-700 hover:underline" href="mailto:{{ c.contact_email }}">{{ c.contact_email }}</a>
              </td>
              <td class="px-4 py-3">
                {% if c.source_url and c.source_url != '#' %}
                <a class="text-fuchsia-700 hover:underline" href="{{ c.source_url }}" target="_blank" rel="noopener">Source</a>
                {% else %}
                <span class="text-slate-400">—</span>
                {% endif %}
              </td>
              <td class="px-4 py-3">
                <form action="/toggle-email/{{ c.id }}" method="post">
                  <button class="px-3 py-1 rounded-full text-xs font-semibold shadow {{ 'bg-gradient-to-r from-emerald-500 to-teal-500 text-white' if c.email_sent else 'bg-gradient-to-r from-slate-200 to-slate-300 text-slate-700' }}">
                    {{ 'Sent' if c.email_sent else 'Not sent' }}
                  </button>
                </form>
              </td>
              <td class="px-4 py-3 text-slate-600">
                {% if c.email_sent_at %}
                  {{ c.email_sent_at.astimezone().strftime('%Y-%m-%d %H:%M') }}
                {% else %}
                  <span class="text-slate-400">—</span>
                {% endif %}
              </td>
              <td class="px-4 py-3">
                <form action="/toggle-reminder/{{ c.id }}" method="post">
                  <button class="px-3 py-1 rounded-full text-xs font-semibold shadow {{ 'bg-gradient-to-r from-indigo-500 to-fuchsia-500 text-white' if c.reminder_sent else 'bg-gradient-to-r from-slate-200 to-slate-300 text-slate-700' }}">
                    {{ 'Sent' if c.reminder_sent else 'Not sent' }}
                  </button>
                </form>
              </td>
              <td class="px-4 py-3">
                <div class="flex items-center gap-2">
                  <a href="/edit/{{ c.id }}" class="px-3 py-1 rounded-lg text-xs font-semibold bg-gradient-to-r from-sky-600 to-indigo-600 text-white shadow hover:opacity-95">Edit</a>
                  <form action="/delete/{{ c.id }}" method="post" onsubmit="return confirm('Delete {{ c.name }}? This cannot be undone.')">
                    <button class="px-3 py-1 rounded-lg text-xs font-semibold bg-gradient-to-r from-rose-600 to-orange-600 text-white shadow hover:opacity-95">Delete</button>
                  </form>
                </div>
              </td>
            </tr>
            {% endfor %}
          </tbody>
        </table>
      </div>
    </section>
  </div>
{% endblock %}
```

---

## templates/edit.html
```html
{% extends "base.html" %}
{% block content %}
  <section class="relative gradient-card rounded-2xl bg-white shadow p-6 max-w-3xl">
    <h2 class="text-lg font-semibold mb-4 bg-clip-text text-transparent bg-gradient-to-r from-indigo-600 via-fuchsia-600 to-emerald-600">Edit contact</h2>
    <form action="/edit/{{ c.id }}" method="post" class="grid md:grid-cols-2 gap-4">
      <label class="grid gap-1">
        <span class="text-xs text-slate-600">Name</span>
        <input name="name" value="{{ c.name }}" required class="px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 focus:ring-sky-400" />
      </label>
      <label class="grid gap-1">
        <span class="text-xs text-slate-600">University</span>
        <input name="university" value="{{ c.university }}" required class="px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 focus:ring-fuchsia-400" />
      </label>
      <label class="grid gap-1 md:col-span-2">
        <span class="text-xs text-slate-600">Research Focus</span>
        <input name="research_focus" value="{{ c.research_focus }}" required class="px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 focus:ring-emerald-400" />
      </label>
      <label class="grid gap-1">
        <span class="text-xs text-slate-600">Contact Email</span>
        <input type="email" name="contact_email" value="{{ c.contact_email }}" required class="px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 focus:ring-sky-400" />
      </label>
      <label class="grid gap-1">
        <span class="text-xs text-slate-600">Source URL</span>
        <input name="source_url" value="{{ c.source_url }}" class="px-3 py-2 rounded-lg border focus:outline-none focus:ring-2 focus:ring-fuchsia-400" />
      </label>

      <div class="flex items-center gap-6 md:col-span-2 mt-2">
        <label class="inline-flex items-center gap-2">
          <input type="checkbox" name="email_sent" {% if c.email_sent %}checked{% endif %} class="h-4 w-4 rounded border-slate-300 text-emerald-600 focus:ring-emerald-500" />
          <span class="text-sm">Email sent</span>
        </label>
        <label class="inline-flex items-center gap-2">
          <input type="checkbox" name="reminder_sent" {% if c.reminder_sent %}checked{% endif %} class="h-4 w-4 rounded border-slate-300 text-fuchsia-600 focus:ring-fuchsia-500" />
          <span class="text-sm">Reminder sent</span>
        </label>
      </div>

      <div class="md:col-span-2 flex items-center gap-3 mt-2">
        <button class="px-4 py-2 rounded-xl bg-gradient-to-r from-sky-600 via-fuchsia-600 to-emerald-600 text-white shadow hover:opacity-95">Save changes</button>
        <a href="/" class="px-4 py-2 rounded-xl border hover:bg-slate-50">Cancel</a>
      </div>
    </form>
  </section>
{% endblock %}
```

---

## static/app.css (optional)
```css
/* Optional enhancements for the RGB look */
.rgb-text { background-image: linear-gradient(90deg,#06b6d4,#8b5cf6,#10b981); -webkit-background-clip: text; background-clip: text; color: transparent; }
.glow { box-shadow: 0 0 0 1px rgba(14,165,233,.15), 0 10px 25px rgba(99,102,241,.15); }
```

---

## tests/test_app.py
```python
import os
import tempfile
from contextlib import contextmanager
from starlette.testclient import TestClient

@contextmanager
def temp_env_db():
    with tempfile.TemporaryDirectory() as d:
        db_path = os.path.join(d, "test.db")
        os.environ["CONTACT_DB"] = db_path
        yield
        os.environ.pop("CONTACT_DB", None)


def make_client():
    # Import inside the function so CONTACT_DB is honored
    from app.main import app
    return TestClient(app)


def test_health_ok():
    with temp_env_db():
        client = make_client()
        r = client.get("/health")
        assert r.status_code == 200
        assert r.json()["status"] == "ok"


def test_add_list_contact():
    with temp_env_db():
        client = make_client()
        # Add
        resp = client.post(
            "/add",
            data=dict(
                name="Ada Lovelace",
                university="Analytical Engine Inst.",
                research_focus="Computing Pioneers",
                contact_email="ada@example.com",
                source_url="https://example.com",
            ),
            allow_redirects=False,
        )
        assert resp.status_code == 303
        # List
        html = client.get("/").text
        assert "Ada Lovelace" in html
        assert "ada@example.com" in html


def test_toggle_email_and_timestamp():
    with temp_env_db():
        client = make_client()
        # Seed has at least one row; toggle first by finding an id from the page
        html = client.get("/").text
        import re
        m = re.search(r"/toggle-email/(\d+)", html)
        assert m, "No contact id found to toggle email"
        cid = int(m.group(1))
        # Toggle
        resp = client.post(f"/toggle-email/{cid}", allow_redirects=False)
        assert resp.status_code == 303
        # Check page shows 'Sent' and a timestamp
        html2 = client.get("/").text
        assert ">Sent<" in html2 or ">Sent</button>" in html2
        assert re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}", html2)


def test_edit_and_delete():
    with temp_env_db():
        client = make_client()
        # Create a new contact to edit/delete
        resp = client.post(
            "/add",
            data=dict(
                name="Grace Hopper",
                university="Navy",
                research_focus="Compilers",
                contact_email="grace@example.com",
                source_url="https://example.com/gh",
            ),
            allow_redirects=False,
        )
        assert resp.status_code == 303
        # Grab its id
        html = client.get("/").text
        import re
        m = re.search(r"/edit/(\d+)">Edit</a>\s*</div>\s*</td>\s*</tr>\s*</tbody>", html)
        # Fallback: find id from delete form if pattern differs
        if not m:
            m = re.search(r"/delete/(\d+)", html)
        assert m, "Could not find contact id for newly added contact"
        cid = int(m.group(1))

        # Edit
        resp2 = client.post(
            f"/edit/{cid}",
            data=dict(
                name="Grace Brewster Hopper",
                university="US Navy",
                research_focus="Compilers & COBOL",
                contact_email="gbhopper@example.com",
                source_url="https://example.com/gbh",
                email_sent="on",
                reminder_sent="on",
            ),
            allow_redirects=False,
        )
        assert resp2.status_code == 303
        html2 = client.get("/").text
        assert "Grace Brewster Hopper" in html2
        assert "gbhopper@example.com" in html2
        assert ">Sent<" in html2

        # Delete
        resp3 = client.post(f"/delete/{cid}", allow_redirects=False)
        assert resp3.status_code == 303
        html3 = client.get("/").text
        assert "Grace Brewster Hopper" not in html3
```

---

## Why that TSX error happened and how this fixes it
- Jinja templates use `{% ... %}` and `{{ ... }}` which look like JSX/TSX to a React/Next bundler.
- If you put `templates/index.html` inside a React project (e.g., `pages/index.tsx`), the bundler tries to parse Jinja and fails with *Unexpected token*.
- This rewrite keeps everything in a **pure FastAPI + Jinja** workspace with `.html` templates only, adds tests, and includes an env‑configurable SQLite path.

If you still see an error after placing files as above, tell me
- the exact command you ran
- the full traceback
- your OS and Python version
so I can zero in on it fast.