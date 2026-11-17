from datetime import datetime, timedelta, timezone

from conftest import ids, login


def test_crm_dedupe_phone_normalisation_and_won_customer(client, ceo):
    c = ids(client, ceo)
    r = client.post("/api/crm/leads", headers=ceo, json={"company_id": c["NES-DM"], "name": "Shop Owner",
                                                          "phone": "0333-1112223", "service": "SEO", "value": 50000})
    assert r.status_code == 201 and r.json()["phone"] == "+923331112223" and r.json()["stage"] == "Inquiry"
    assert r.json()["score"] > 0
    dup = client.post("/api/crm/leads", headers=ceo, json={"company_id": c["NES-DM"], "name": "Same person",
                                                            "phone": "+92 333 1112223"})
    assert dup.status_code == 409
    lid = r.json()["id"]
    assert client.patch(f"/api/crm/leads/{lid}", headers=ceo, json={"stage": "Nope"}).status_code == 400
    client.post("/api/crm/activities", headers=ceo, json={"lead_id": lid, "channel": "whatsapp", "summary": "Sent intro"})
    won = client.patch(f"/api/crm/leads/{lid}", headers=ceo, json={"stage": "Onboarding", "status": "won"}).json()
    assert won["customer_id"]
    hist = client.get(f"/api/crm/history?lead_id={lid}", headers=ceo).json()
    assert hist[0]["summary"] == "Sent intro"


def test_finance_summary_invoice_and_payment(client, ceo):
    c = ids(client, ceo)
    today = datetime.now(timezone.utc).date().isoformat()
    client.post("/api/finance/entries", headers=ceo, json={"company_id": c["NES-DM"], "kind": "revenue", "amount": 100000,
                                                            "service": "SEO", "occurred_on": today})
    client.post("/api/finance/entries", headers=ceo, json={"company_id": c["NES-DM"], "kind": "expense", "amount": 30000,
                                                            "occurred_on": today})
    usd = client.post("/api/finance/entries", headers=ceo, json={"company_id": c["NES-DM"], "kind": "revenue", "amount": 100,
                                                                  "currency": "USD", "fx_to_pkr": 280, "occurred_on": today,
                                                                  "service": "Meta Ads"})
    assert usd.status_code == 201
    s = client.get("/api/finance/summary", headers=ceo).json()
    dm = next(x for x in s["by_company"] if x["company"] == "NES Digital Marketing")
    assert dm["revenue"] == 128000 and dm["net"] == 98000
    inv = client.post("/api/finance/invoices", headers=ceo, json={"company_id": c["NES-DM"], "amount": 20000}).json()
    assert inv["number"].startswith("NES-DM-")
    assert client.post(f"/api/finance/invoices/{inv['id']}/payment", headers=ceo, json={"amount": 25000}).status_code == 400
    assert client.post(f"/api/finance/invoices/{inv['id']}/payment", headers=ceo, json={"amount": 5000}).json()["status"] == "partial"
    d = login(client, "HEADSALES")
    assert client.get("/api/finance/entries", headers=d).status_code == 403


def test_workforce_recommendations_respect_level(client, ceo):
    c = ids(client, ceo)
    depts = {d["code"]: d["id"] for d in client.get(f"/api/departments?company_id={c['NES-DM']}", headers=ceo).json()}
    people = {p["employee_code"]: p for p in client.get("/api/people", headers=ceo).json()}
    client.post("/api/tasks", headers=ceo, json={"company_id": c["NES-DM"], "department_id": depts["SALES"],
                                                 "title": "Complex SEO strategy", "complexity": "complex",
                                                 "required_skills": ["seo"], "estimated_hours": 4})
    basic = client.post("/api/tasks", headers=ceo, json={"company_id": c["NES-DM"], "department_id": depts["SALES"],
                                                         "title": "Basic keyword list", "complexity": "basic",
                                                         "required_skills": ["seo"], "estimated_hours": 2}).json()
    wf = client.get("/api/workforce", headers=login(client, "HEADSALES")).json()
    recs = {r["task"]: r for r in wf["workforce"]["recommendations"]}
    assert "Complex SEO strategy" not in recs or recs["Complex SEO strategy"]["person"] != "DM Beginner"
    assert "Basic keyword list" in recs
    r = client.post("/api/workforce/apply", headers=login(client, "HEADSALES"),
                    json={"task_id": basic["id"], "person_id": people["BEG1"]["id"]}).json()
    assert r["assignee_person_id"] == people["BEG1"]["id"] and r["reviewer_person_id"]


def test_onboarding_creates_real_work(client, ceo):
    c = ids(client, ceo)
    people = {p["employee_code"]: p for p in client.get("/api/people", headers=ceo).json()}
    p = client.post("/api/people", headers=ceo, json={"full_name": "New Trainee", "company_id": c["NES-DM"],
                                                      "category": "trainee", "skill_level": "beginner",
                                                      "manager_id": people["HEADSALES"]["id"],
                                                      "training_requirements": ["Meta Ads basics"]}).json()
    tasks = client.get(f"/api/tasks?assignee_person_id={p['id']}", headers=ceo).json()
    titles = {t["title"] for t in tasks}
    assert "Training: Meta Ads basics" in titles and any("Shadow" in t for t in titles)
    acc = client.post(f"/api/people/{p['id']}/account", headers=ceo,
                      json={"email": "trainee@t.test", "role": "intern", "temporary_password": "weak"})
    assert acc.status_code == 422 or acc.status_code == 400
    acc = client.post(f"/api/people/{p['id']}/account", headers=ceo,
                      json={"email": "trainee@t.test", "role": "intern", "temporary_password": "Strong-Pass-2026"})
    assert acc.status_code == 201
    assert client.post("/api/people", headers=ceo, json={"full_name": "x", "company_id": c["NES-DM"],
                                                         "category": "astronaut"}).status_code == 400


def test_attendance(client, ceo):
    h = login(client, "EMP1")
    r = client.post("/api/attendance/check-in", headers=h)
    assert r.status_code == 200 and r.json()["status"] in {"present", "late"}
    assert client.post("/api/attendance/check-in", headers=h).status_code == 409
    assert client.post("/api/attendance/check-out", headers=h).status_code == 200
    att = client.get("/api/attendance", headers=ceo).json()
    assert any(r["name"] == "DM Employee" and r["status"] != "unmarked" for r in att["records"])


def test_projects_and_dashboard(client, ceo):
    c = ids(client, ceo)
    p = client.post("/api/projects", headers=ceo, json={"company_id": c["NES-CONS"], "name": "Embassy Appointment Department",
                                                        "budget": 100000, "deadline": "2020-01-01"}).json()
    client.post(f"/api/projects/{p['id']}/milestones", headers=ceo, json={"title": "Hire 2 staff"})
    t = client.post("/api/tasks", headers=ceo, json={"company_id": c["NES-CONS"], "project_id": p["id"], "title": "Set up",
                                                     "due_at": (datetime.now(timezone.utc) - timedelta(days=2)).isoformat()})
    d = client.get("/api/dashboard", headers=ceo).json()
    s = d["snapshot"]
    assert s["tasks"]["overdue"] >= 1
    proj = next(x for x in s["projects"] if x["name"] == "Embassy Appointment Department")
    assert proj["needs_attention"] and "past deadline" in proj["why"]
    assert any(a["title"].startswith("Project needs attention") for a in s["alerts"])
    assert d["health"]["database"] == "CONNECTED"
    r = client.post("/api/assistant/ask", headers=ceo, json={"question": "Which projects require my attention?"}).json()
    assert "Embassy Appointment Department" in r["answer"]


def test_integration_status_cannot_be_faked(client, ceo):
    assert client.patch("/api/integrations/google_gmail", headers=ceo, json={"status": "CONNECTED"}).status_code == 400
    assert client.patch("/api/integrations/google_gmail", headers=ceo, json={"status": "PAUSED"}).json()["status"] == "PAUSED"
