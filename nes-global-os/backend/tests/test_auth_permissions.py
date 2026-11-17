import pyotp

from conftest import PW, ids, login


def test_login_wrong_password_and_lockout(client):
    for _ in range(5):
        r = client.post("/api/auth/login", json={"email": "cons1@t.test", "password": "wrong-password"})
        assert r.status_code == 401
    r = client.post("/api/auth/login", json={"email": "cons1@t.test", "password": PW})
    assert r.status_code == 423  # locked even with the right password
    from app.db import SessionLocal
    from app import models as m
    from sqlalchemy import select
    with SessionLocal() as db:
        u = db.scalar(select(m.User).where(m.User.email == "cons1@t.test"))
        u.locked_until = None
        db.commit()


def test_unauthenticated_is_rejected(client):
    assert client.get("/api/dashboard").status_code == 401
    assert client.get("/api/dashboard", headers={"authorization": "Bearer junk"}).status_code == 401


def test_cookie_session_and_me(client):
    r = client.post("/api/auth/login", json={"email": "ceo@t.test", "password": PW})
    assert r.status_code == 200 and "nes_session" in r.cookies
    me = client.get("/api/auth/me").json()
    assert me["user"]["role"] == "ceo" and "password_hash" not in me["user"]
    assert me["scope"]["all_companies"] is True


def test_mfa_flow(client):
    h = login(client, "DIRDM")
    secret = client.post("/api/auth/mfa/setup", headers=h).json()["secret"]
    assert client.post("/api/auth/mfa/enable", headers=h, json={"code": "000000"}).status_code == 400
    assert client.post("/api/auth/mfa/enable", headers=h, json={"code": pyotp.TOTP(secret).now()}).status_code == 200
    r = client.post("/api/auth/login", json={"email": "dirdm@t.test", "password": PW})
    assert r.status_code == 401 and r.json()["detail"]["mfa_required"]
    r = client.post("/api/auth/login", json={"email": "dirdm@t.test", "password": PW, "mfa_code": pyotp.TOTP(secret).now()})
    assert r.status_code == 200
    h = {"authorization": f"Bearer {r.json()['token']}"}
    assert client.post("/api/auth/mfa/disable", headers=h,
                       json={"code": pyotp.TOTP(secret).now(), "password": PW}).status_code == 200


def test_role_matrix(client):
    emp = login(client, "EMP1")
    assert client.get("/api/dashboard", headers=emp).status_code == 403
    assert client.get("/api/finance/summary", headers=emp).status_code == 403
    assert client.get("/api/ai/providers", headers=emp).status_code == 403
    head = login(client, "HEADSALES")
    assert client.get("/api/dashboard", headers=head).status_code == 200
    assert client.put("/api/ai/budget", headers=head, json={"monthly_limit_usd": 1}).status_code == 403


def test_multi_company_isolation(client, ceo):
    c = ids(client, ceo)
    lead = client.post("/api/crm/leads", headers=ceo, json={"company_id": c["NES-CONS"], "name": "Ali Student",
                                                             "phone": "0300 1234567", "service": "UK admission"})
    assert lead.status_code == 201
    d = login(client, "DIRDM")
    # director of Digital Marketing cannot see or touch Consultancy data
    assert {x["code"] for x in client.get("/api/companies", headers=d).json()} == {"NES-DM"}
    assert all(l["company_id"] == c["NES-DM"] for l in client.get("/api/crm/leads", headers=d).json())
    assert client.patch(f"/api/crm/leads/{lead.json()['id']}", headers=d, json={"notes": "x"}).status_code == 403
    assert client.post("/api/crm/leads", headers=d, json={"company_id": c["NES-CONS"], "name": "x"}).status_code == 403
    dash = client.get("/api/dashboard", headers=d).json()["snapshot"]
    assert [x["code"] for x in dash["companies"]] == ["NES-DM"]
    # group reports are CEO-only
    assert client.get("/api/reports", headers=d).status_code == 403


def test_employee_sees_and_edits_only_own_tasks(client, ceo):
    c = ids(client, ceo)
    people = {p["employee_code"]: p for p in client.get("/api/people", headers=ceo).json()}
    mine = client.post("/api/tasks", headers=ceo, json={"company_id": c["NES-DM"], "title": "Write SEO audit",
                                                        "assignee_person_id": people["EMP1"]["id"]}).json()
    other = client.post("/api/tasks", headers=ceo, json={"company_id": c["NES-DM"], "title": "Someone else's",
                                                         "assignee_person_id": people["BEG1"]["id"]}).json()
    emp = login(client, "EMP1")
    titles = [t["title"] for t in client.get("/api/tasks", headers=emp).json()]
    assert "Write SEO audit" in titles and "Someone else's" not in titles
    assert client.patch(f"/api/tasks/{mine['id']}", headers=emp, json={"status": "in_progress"}).status_code == 200
    assert client.patch(f"/api/tasks/{mine['id']}", headers=emp, json={"title": "hacked"}).status_code == 403
    assert client.patch(f"/api/tasks/{other['id']}", headers=emp, json={"status": "done"}).status_code == 403


def test_supervised_work_goes_to_review(client, ceo):
    c = ids(client, ceo)
    people = {p["employee_code"]: p for p in client.get("/api/people", headers=ceo).json()}
    t = client.post("/api/tasks", headers=ceo, json={"company_id": c["NES-DM"], "title": "Beginner task",
                                                     "assignee_person_id": people["BEG1"]["id"],
                                                     "reviewer_person_id": people["HEADSALES"]["id"]}).json()
    beg = login(client, "BEG1")
    r = client.patch(f"/api/tasks/{t['id']}", headers=beg, json={"status": "done"})
    assert r.json()["status"] == "review"


def test_audit_log_records_actions(client, ceo):
    log = client.get("/api/audit", headers=ceo).json()
    actions = {a["action"] for a in log}
    assert {"auth.login", "lead.create", "task.create"} <= actions
