"""Administration CLI.

  python -m app.cli seed                       # company structure, departments, pipelines, agent registry
  python -m app.cli create-ceo --email you@x   # prompts for a password (never pass it on the command line)
  python -m app.cli backup-recorded            # called by deploy/backup.sh after a successful backup
"""
from __future__ import annotations

import argparse
import getpass
import os
import sys
from datetime import datetime, timezone

from sqlalchemy import func, select

from . import models as m
from .ai.runtime import put_setting
from .db import SessionLocal
from .reports import EXEC_CODE
from .security import hash_password, validate_password_strength
from .seed import seed


def create_ceo(email: str, name: str) -> None:
    pw = os.getenv("NES_CEO_PASSWORD") or getpass.getpass("New CEO password: ")
    if not os.getenv("NES_CEO_PASSWORD") and pw != getpass.getpass("Repeat password: "):
        sys.exit("Passwords do not match")
    err = validate_password_strength(pw)
    if err:
        sys.exit(err)
    with SessionLocal() as db:
        if db.scalar(select(m.User).where(m.User.role == "ceo")):
            sys.exit("A CEO account already exists")
        parent = db.scalar(select(m.Company).where(m.Company.code == "NES-GROUP"))
        if not parent:
            sys.exit("Run `seed` first")
        exec_dept = db.scalar(select(m.Department).where(m.Department.company_id == parent.id, m.Department.code == "EXEC"))
        n = (db.scalar(select(func.count()).select_from(m.Person)) or 0) + 1
        p = m.Person(employee_code=f"GROUP-{n:04d}", full_name=name, email=email.lower(), category="director",
                     designation="Chief Executive Officer", company_id=parent.id,
                     department_id=exec_dept.id if exec_dept else None, skill_level="department_head", status="active")
        db.add(p)
        db.flush()
        if exec_dept:
            exec_dept.head_person_id = p.id
        db.add(m.User(email=email.lower(), password_hash=hash_password(pw), role="ceo", person_id=p.id))
        ea = db.scalar(select(m.Agent).where(m.Agent.code == EXEC_CODE))
        if ea:
            ea.supervisor_person_id = p.id
        db.commit()
    print(f"CEO account created for {email}. Sign in and enable MFA under Settings → Security.")


def main() -> None:
    ap = argparse.ArgumentParser(prog="nes")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("seed")
    c = sub.add_parser("create-ceo")
    c.add_argument("--email", required=True)
    c.add_argument("--name", default="Mubshair Ali")
    b = sub.add_parser("backup-recorded")
    b.add_argument("--file", required=True)
    a = ap.parse_args()
    if a.cmd == "seed":
        with SessionLocal() as db:
            print("Seeded:", seed(db))
    elif a.cmd == "create-ceo":
        create_ceo(a.email, a.name)
    elif a.cmd == "backup-recorded":
        with SessionLocal() as db:
            put_setting(db, "last_backup", {"at": datetime.now(timezone.utc).isoformat(), "file": a.file})
            db.commit()


if __name__ == "__main__":
    main()
