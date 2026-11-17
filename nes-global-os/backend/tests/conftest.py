"""Tests run against a real PostgreSQL database (NES_TEST_DATABASE_URL), migrated with Alembic."""
from __future__ import annotations

import os

os.environ["NES_DATABASE_URL"] = os.getenv("NES_TEST_DATABASE_URL",
                                           "postgresql+psycopg://postgres@127.0.0.1:5432/nesos_test")
os.environ.setdefault("NES_REDIS_URL", "redis://127.0.0.1:6379/15")
os.environ["NES_LOGIN_RATE_LIMIT"] = "1000"
os.environ["NES_CALL_RING_SECONDS"] = "2"
import tempfile  # noqa: E402
os.environ["NES_FILES_DIR"] = tempfile.mkdtemp(prefix="nes-files-")
for p in ("ANTHROPIC", "OPENAI", "GEMINI", "OPENAI_COMPATIBLE"):
    os.environ.pop(f"NES_{p}_API_KEY", None)

import json  # noqa: E402

import httpx  # noqa: E402
import pytest  # noqa: E402
from alembic import command  # noqa: E402
from alembic.config import Config  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select, text  # noqa: E402

from app import models as m  # noqa: E402
from app.ai import providers  # noqa: E402
from app.db import SessionLocal, engine  # noqa: E402
from app.deps import get_redis  # noqa: E402
from app.main import app  # noqa: E402
from app.security import hash_password  # noqa: E402
from app.seed import seed  # noqa: E402

PW = "Test-Password-2026!"
HERE = os.path.dirname(os.path.dirname(__file__))


@pytest.fixture(scope="session", autouse=True)
def database():
    with engine.begin() as c:
        c.execute(text("drop schema public cascade; create schema public;"))
    cfg = Config(os.path.join(HERE, "alembic.ini"))
    cfg.set_main_option("script_location", os.path.join(HERE, "alembic"))
    command.upgrade(cfg, "head")
    r = get_redis()
    if r:
        r.flushdb()
    with SessionLocal() as db:
        seed(db)
        comps = {c.code: c for c in db.scalars(select(m.Company))}
        depts = {(d.company_id, d.code): d for d in db.scalars(select(m.Department))}

        def person(code, name, comp, dept, role, level="intermediate", cat="permanent", skills=()):
            p = m.Person(employee_code=code, full_name=name, company_id=comps[comp].id,
                         department_id=depts[(comps[comp].id, dept)].id if dept else None,
                         skill_level=level, category=cat, skills=list(skills), status="active",
                         weekly_capacity_hours=40)
            db.add(p)
            db.flush()
            if role:
                db.add(m.User(email=f"{code.lower()}@t.test", password_hash=hash_password(PW), role=role, person_id=p.id))
            return p

        person("CEO", "Mubshair Ali", "NES-GROUP", "EXEC", "ceo", "department_head", "director")
        person("DIRDM", "DM Director", "NES-DM", None, "director", "expert", "director")
        head = person("HEADSALES", "DM Sales Head", "NES-DM", "SALES", "dept_head", "department_head")
        person("EMP1", "DM Employee", "NES-DM", "SALES", "employee", "intermediate", skills=["seo", "copywriting"])
        person("BEG1", "DM Beginner", "NES-DM", "SALES", "intern", "beginner", "intern", skills=["seo"])
        person("CONS1", "Consultancy Employee", "NES-CONS", "STUDY", "employee")
        db.commit()
    yield


@pytest.fixture
def client():
    with TestClient(app) as c:
        yield c


def login(client, code: str) -> dict:
    r = client.post("/api/auth/login", json={"email": f"{code.lower()}@t.test", "password": PW})
    assert r.status_code == 200, r.text
    return {"authorization": f"Bearer {r.json()['token']}"}


@pytest.fixture
def ceo(client):
    return login(client, "CEO")


def ids(client, h) -> dict:
    comps = {c["code"]: c["id"] for c in client.get("/api/companies", headers=h).json()}
    return comps


class FakeLLM:
    """httpx MockTransport that imitates the provider APIs."""

    def __init__(self):
        self.mode = {}  # provider -> "ok" | "auth" | "quota" | "down"
        self.reply = "Done. Here is the deliverable."
        self.calls = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        host = request.url.host
        prov = "anthropic" if "anthropic" in host else "gemini" if "google" in host else "openai"
        body = json.loads(request.content)
        self.calls.append((prov, body))
        mode = self.mode.get(prov, "ok")
        if mode == "auth":
            return httpx.Response(401, json={"error": "invalid x-api-key"})
        if mode == "quota":
            return httpx.Response(429, json={"error": "rate_limit"})
        if mode == "down":
            return httpx.Response(529, json={"error": "overloaded"})
        if prov == "anthropic":
            return httpx.Response(200, json={"content": [{"type": "text", "text": self.reply}],
                                             "usage": {"input_tokens": 1000, "output_tokens": 500}})
        return httpx.Response(200, json={"choices": [{"message": {"content": self.reply}}],
                                         "usage": {"prompt_tokens": 1000, "completion_tokens": 500}})


@pytest.fixture
def llm():
    fake = FakeLLM()
    providers.transport = httpx.MockTransport(fake)
    yield fake
    providers.transport = None
