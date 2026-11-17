"""Employee app (NES Team) API."""
from datetime import date, timedelta

from sqlalchemy import select

from app import models as m
from app.db import SessionLocal
from conftest import PW, ids, login

OFFICE = (32.5833, 73.4833)  # test coordinates (Mandi Bahauddin area)


def mlogin(client, code):
    r = client.post("/api/mobile/login", json={"email": f"{code.lower()}@t.test", "password": PW,
                                               "device_name": f"{code} phone", "platform": "android", "app_version": "1.0.0"})
    assert r.status_code == 200, r.text
    return {"authorization": f"Bearer {r.json()['token']}"}, r.json()["device_id"]


def people(client, ceo):
    return {p["employee_code"]: p for p in client.get("/api/people", headers=ceo).json()}


def test_config_and_device_revoke_wipes(client, ceo):
    assert client.get("/api/mobile/config").json()["system"] == "NES GLOBAL OS"
    h, did = mlogin(client, "CONS1")
    assert client.get("/api/mobile/home", headers=h).status_code == 200
    devs = client.get("/api/hub/devices", headers=ceo).json()
    assert any(d["id"] == did and d["user"] == "Consultancy Employee" for d in devs)
    assert client.get("/api/hub/devices", headers=login(client, "EMP1")).status_code == 403
    client.post(f"/api/hub/devices/{did}/revoke", headers=ceo, json={"wipe": True})
    r = client.get("/api/mobile/home", headers=h)
    assert r.status_code == 401 and r.json()["detail"]["device_revoked"] and r.json()["detail"]["wipe"]
    # the same install signing in again reuses its device entry
    body = {"email": "cons1@t.test", "password": PW, "install_id": "install-abc", "device_name": "Pixel"}
    d1 = client.post("/api/mobile/login", json=body).json()["device_id"]
    d2 = client.post("/api/mobile/login", json=body).json()["device_id"]
    assert d1 == d2


def test_geofenced_checkin_flow(client, ceo):
    c = ids(client, ceo)
    h, _ = mlogin(client, "BEG1")
    # biometric + GPS quality rules
    base = {"lat": OFFICE[0], "lng": OFFICE[1], "accuracy_m": 15}
    assert client.post("/api/mobile/attendance/check-in", headers=h, json=base).status_code == 400
    assert "weak" in client.post("/api/mobile/attendance/check-in", headers=h,
                                 json={**base, "accuracy_m": 900, "biometric_confirmed": True}).text
    site = client.post("/api/hub/sites", headers=ceo, json={"name": "DM Office", "company_id": c["NES-DM"],
                                                             "lat": OFFICE[0], "lng": OFFICE[1], "radius_m": 100}).json()
    assert site["radius_m"] == 100
    far = {"lat": OFFICE[0] + 0.02, "lng": OFFICE[1], "accuracy_m": 10, "biometric_confirmed": True}  # ~2.2 km away
    r = client.post("/api/mobile/attendance/check-in", headers=h, json=far)
    assert r.status_code == 422 and r.json()["detail"]["outside_geofence"] and r.json()["detail"]["distance_m"] > 2000
    r = client.post("/api/mobile/attendance/check-in", headers=h, json={**far, "field_note": "At client: City Mall"})
    assert r.status_code == 200
    att = r.json()["attendance"]
    assert att["status"] == "remote" and att["outside_geofence"] and att["field_approved"] is None
    assert client.post("/api/mobile/attendance/check-in", headers=h, json={**base, "biometric_confirmed": True}).status_code == 409
    # department head reviews the field check-in; the employee can't
    assert client.get("/api/mobile/approvals", headers=h).json()["field_checkins"] == []
    head, _ = mlogin(client, "HEADSALES")
    fc = client.get("/api/mobile/approvals", headers=head).json()["field_checkins"]
    assert len(fc) == 1 and fc[0]["person"]["name"] == "DM Beginner" and "maps.google.com" in fc[0]["map"]
    assert client.post(f"/api/mobile/attendance/{fc[0]['id']}/field-decide", headers=h, json={"decision": "approved"}).status_code == 403
    ok = client.post(f"/api/mobile/attendance/{fc[0]['id']}/field-decide", headers=head, json={"decision": "approved"}).json()
    assert ok["field_approved"] is True
    assert client.post("/api/mobile/attendance/check-out", headers=h, json={"lat": OFFICE[0], "lng": OFFICE[1]}).status_code == 200
    # a consultancy employee is not covered by the DM-only site → inside check-in impossible there, but
    # web check-in is now blocked because sites exist
    assert "NES Team app" in client.post("/api/attendance/check-in", headers=login(client, "CONS1")).text


def test_inside_geofence_present_or_late(client, ceo):
    c = ids(client, ceo)
    client.post("/api/hub/sites", headers=ceo, json={"name": "Consultancy Office", "company_id": c["NES-CONS"],
                                                      "lat": OFFICE[0] + 0.1, "lng": OFFICE[1], "radius_m": 150})
    h, _ = mlogin(client, "CONS1")
    near = {"lat": OFFICE[0] + 0.1 + 0.0009, "lng": OFFICE[1], "accuracy_m": 20, "biometric_confirmed": True}  # ~100 m
    r = client.post("/api/mobile/attendance/check-in", headers=h, json=near).json()
    assert r["site"] == "Consultancy Office" and r["attendance"]["status"] in {"present", "late"}
    assert r["attendance"]["outside_geofence"] is False and r["attendance"]["distance_m"] < 150
    hist = client.get("/api/mobile/attendance/history", headers=h).json()
    assert hist["records"][0]["method"] == "mobile"


def test_leave_balances_requests_and_approval(client, ceo):
    h, _ = mlogin(client, "EMP1")
    lv = client.get("/api/mobile/leave", headers=h).json()
    casual = next(b for b in lv["balances"] if b["kind"] == "casual")
    assert casual["entitled"] == 10 and casual["remaining"] == 10
    # next Monday–Wednesday = 3 working days
    d = date.today() + timedelta(days=(7 - date.today().weekday()) % 7 or 7)
    r = client.post("/api/mobile/leave", headers=h, json={"kind": "casual", "start_on": str(d), "end_on": str(d + timedelta(days=2)),
                                                          "reason": "Family event"})
    assert r.status_code == 201 and r.json()["days"] == 3 and r.json()["status"] == "pending"
    lid = r.json()["id"]
    assert client.post("/api/mobile/leave", headers=h, json={"kind": "sick", "start_on": str(d + timedelta(days=1)),
                                                             "end_on": str(d + timedelta(days=1))}).status_code == 409
    too_much = client.post("/api/mobile/leave", headers=h, json={"kind": "casual", "start_on": str(d + timedelta(days=14)),
                                                                 "end_on": str(d + timedelta(days=27))})
    assert too_much.status_code == 400 and "Not enough" in too_much.text
    assert client.post("/api/mobile/leave", headers=h, json={"kind": "overtime", "start_on": str(d), "end_on": str(d)}).status_code == 400
    assert client.post("/api/mobile/leave", headers=h, json={"kind": "overtime", "start_on": str(d - timedelta(days=3)),
                                                             "end_on": str(d - timedelta(days=3)), "hours": 2}).status_code == 201
    # employee can't approve their own; consultancy staff can't; DM department head can
    assert client.post(f"/api/mobile/leave/{lid}/decide", headers=h, json={"decision": "approved"}).status_code == 403
    cons, _ = mlogin(client, "CONS1")
    assert client.post(f"/api/mobile/leave/{lid}/decide", headers=cons, json={"decision": "approved"}).status_code == 403
    head, _ = mlogin(client, "HEADSALES")
    assert any(x["id"] == lid for x in client.get("/api/mobile/approvals", headers=head).json()["leave"])
    ok = client.post(f"/api/mobile/leave/{lid}/decide", headers=head, json={"decision": "approved"}).json()
    assert ok["status"] == "approved"
    casual = next(b for b in client.get("/api/mobile/leave", headers=h).json()["balances"] if b["kind"] == "casual")
    assert casual["used"] == 3 and casual["remaining"] == 7
    with SessionLocal() as db:
        emp = db.scalar(select(m.Person).where(m.Person.employee_code == "EMP1"))
        days = list(db.scalars(select(m.Attendance).where(m.Attendance.person_id == emp.id, m.Attendance.status == "leave")))
        assert len(days) == 3
    assert client.post(f"/api/mobile/leave/{lid}/cancel", headers=h).status_code == 409


def test_shifts(client, ceo):
    head, _ = mlogin(client, "HEADSALES")
    emp = people(client, ceo)["EMP1"]
    tomorrow = date.today() + timedelta(days=1)
    assert client.put("/api/mobile/shifts", headers=head, json={"person_id": emp["id"], "day": str(tomorrow),
                                                                "start_time": "11:00", "end_time": "19:00"}).status_code == 200
    h, _ = mlogin(client, "EMP1")
    week = client.get("/api/mobile/shifts", headers=h).json()
    assert week[1]["start"] == "11:00" and week[1]["custom"]
    assert client.put("/api/mobile/shifts", headers=h, json={"person_id": emp["id"], "day": str(tomorrow),
                                                             "start_time": "09:00", "end_time": "10:00"}).status_code == 403
    team = client.get(f"/api/mobile/shifts/team?day={tomorrow}", headers=head).json()["team"]
    assert any(t["person"]["name"] == "DM Employee" and t["shift"]["start"] == "11:00" for t in team)


def test_directory_news_chat(client, ceo):
    h, _ = mlogin(client, "EMP1")
    names = {p["name"] for p in client.get("/api/mobile/directory", headers=h).json()}
    assert {"Mubshair Ali", "Consultancy Employee"} <= names
    assert [p["name"] for p in client.get("/api/mobile/directory?q=consult", headers=h).json()] == ["Consultancy Employee"]
    # news permissions + visibility
    c = ids(client, ceo)
    assert client.post("/api/mobile/news", headers=ceo, json={"title": "Office closed Friday", "body": "Public holiday.",
                                                             "priority": "urgent"}).status_code == 201
    head, _ = mlogin(client, "HEADSALES")
    assert client.post("/api/mobile/news", headers=head, json={"title": "Group notice", "body": "y"}).status_code == 403
    assert client.post("/api/mobile/news", headers=h, json={"title": "Group notice", "body": "y", "company_id": c["NES-DM"]}).status_code == 403
    dm_depts = {d["code"]: d["id"] for d in client.get(f"/api/departments?company_id={c['NES-DM']}", headers=ceo).json()}
    assert client.post("/api/mobile/news", headers=head, json={"title": "Sales meeting 4pm", "body": "Room 2",
                                                               "department_id": dm_depts["SALES"]}).status_code == 201
    titles = [n["title"] for n in client.get("/api/mobile/news", headers=h).json()]
    assert "Office closed Friday" in titles and "Sales meeting 4pm" in titles
    cons, _ = mlogin(client, "CONS1")
    cons_titles = [n["title"] for n in client.get("/api/mobile/news", headers=cons).json()]
    assert "Office closed Friday" in cons_titles and "Sales meeting 4pm" not in cons_titles
    sync = client.get("/api/mobile/sync", headers=cons).json()
    assert any(n["title"] == "Office closed Friday" for n in sync["new_urgent"]) and sync["unread_news"] >= 1
    nid = next(n["id"] for n in client.get("/api/mobile/news", headers=cons).json() if n["title"] == "Office closed Friday")
    client.post(f"/api/mobile/news/{nid}/read", headers=cons)
    assert next(n for n in client.get("/api/mobile/news", headers=cons).json() if n["id"] == nid)["read"]
    # chat: default channels + department isolation + DM + encryption at rest
    chans = {c_["kind"]: c_ for c_ in client.get("/api/mobile/chat/channels", headers=h).json()}
    assert {"all", "company", "department"} <= set(chans)
    dept_ch = chans["department"]["id"]
    assert client.post(f"/api/mobile/chat/{dept_ch}/messages", headers=h, json={"body": "Secret sales plan"}).status_code == 201
    assert client.get(f"/api/mobile/chat/{dept_ch}/messages", headers=cons).status_code == 403
    beg, _ = mlogin(client, "BEG1")
    beg_dept = next(c_ for c_ in client.get("/api/mobile/chat/channels", headers=beg).json() if c_["kind"] == "department")
    assert beg_dept["id"] == dept_ch and beg_dept["unread"] == 1
    cons_user = next(p["user_id"] for p in client.get("/api/mobile/directory", headers=h).json() if p["name"] == "Consultancy Employee")
    dm = client.post("/api/mobile/chat/direct", headers=h, json={"user_id": cons_user}).json()
    assert dm["title"] == "Consultancy Employee"
    assert client.post("/api/mobile/chat/direct", headers=h, json={"user_id": cons_user}).json()["id"] == dm["id"]
    client.post(f"/api/mobile/chat/{dm['id']}/messages", headers=h, json={"body": "Hi from sales"})
    got = client.get(f"/api/mobile/chat/{dm['id']}/messages", headers=cons).json()
    assert got["messages"][-1]["body"] == "Hi from sales" and got["channel"]["title"] == "DM Employee"
    assert client.get(f"/api/mobile/chat/{dm['id']}/messages", headers=beg).status_code == 403
    with SessionLocal() as db:
        raw = [x.body_enc for x in db.scalars(select(m.ChatMessage))]
        assert raw and all("Secret sales plan" not in b and "Hi from sales" not in b for b in raw)


def test_documents_and_help_desk(client, ceo):
    c = ids(client, ceo)
    policy = ("NES Travel Reimbursement Policy\nEmployees travelling for client work are reimbursed PKR 25 per km "
              "for own vehicle. Submit receipts within 7 days. Casual leave must be requested one day in advance.")
    r = client.post("/api/hub/documents", headers=ceo, data={"title": "Travel Reimbursement Policy", "category": "policy"},
                    files={"file": ("travel.txt", policy.encode(), "text/plain")})
    assert r.status_code == 201 and r.json()["sha256"] and "PKR 25" in r.json()["body_text"]
    client.post("/api/hub/documents", headers=ceo, data={"title": "Salary bands (leaders)", "category": "policy",
                                                          "leaders_only": "true", "body_text": "Confidential bands"})
    bad = client.post("/api/hub/documents", headers=ceo, data={"title": "x", "category": "policy"},
                      files={"file": ("virus.exe", b"MZ....", "application/octet-stream")})
    assert bad.status_code == 400
    fake = client.post("/api/hub/documents", headers=ceo, data={"title": "x", "category": "policy"},
                       files={"file": ("fake.pdf", b"not a pdf", "application/pdf")})
    assert fake.status_code == 400 and "match" in fake.text
    emp = login(client, "EMP1")
    assert client.post("/api/hub/documents", headers=emp, data={"title": "x", "category": "policy", "body_text": "y"}).status_code == 403
    h, _ = mlogin(client, "EMP1")
    docs = client.get("/api/mobile/documents", headers=h).json()
    titles = [d["title"] for d in docs]
    assert "Travel Reimbursement Policy" in titles and "Salary bands (leaders)" not in titles
    did = next(d["id"] for d in docs if d["title"] == "Travel Reimbursement Policy")
    link = client.post(f"/api/mobile/documents/{did}/link", headers=h).json()["path"]
    f = client.get(link)
    assert f.status_code == 200 and b"PKR 25" in f.content
    assert client.get(f"/api/files/{did}?t=forged").status_code == 403
    # help desk: own data, then policy search (no AI connected → data/document answer, never invented)
    a = client.post("/api/mobile/assistant", headers=h, json={"question": "How many casual leaves do I have left?"}).json()
    assert "7" in a["answer"] and a["source"] == "data" and a["sources"] == []
    a = client.post("/api/mobile/assistant", headers=h, json={"question": "What is the travel reimbursement policy?"}).json()
    assert "PKR 25" in a["answer"] and a["sources"][0]["title"] == "Travel Reimbursement Policy"
    a = client.post("/api/mobile/assistant", headers=h, json={"question": "Where is my payslip?"}).json()
    assert "not in NES GLOBAL OS yet" in a["answer"]


def test_home_summary(client, ceo):
    h, _ = mlogin(client, "EMP1")
    home = client.get("/api/mobile/home", headers=h).json()
    assert home["person"]["name"] == "DM Employee" and home["is_leader"] is False
    assert {b["kind"] for b in home["leave_balances"]} == {"annual", "casual", "sick"}
    head, _ = mlogin(client, "HEADSALES")
    assert client.get("/api/mobile/home", headers=head).json()["is_leader"] is True
