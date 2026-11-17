"""Initial company structure (from the Nov 2026 website audit) and the AI agent registry.

Rules followed: no invented company facts — contact details are exactly as published on the sites.
No business figures are seeded. Agents are seeded as CONFIGURED (not active): each must pass a live
test with a connected AI provider before it can be activated.
"""
from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m
from .reports import EXEC_CODE
from .routers.system import DAILY_OPS_DEFAULT, INTEGRATIONS
from .ai.runtime import put_setting

OPUS, SONNET, HAIKU = "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5"

COMPANIES = [
    dict(code="NES-GROUP", name="NADIR E-SKILLS (SMC-PRIVATE) LIMITED", kind="parent",
         description="Parent company. Business & skills ecosystem: digital skills training, study abroad guidance, "
                     "websites and branding, marketing and events.",
         website="https://nadireskills.com", phone="03400 524444", whatsapp="+92 341 7749005",
         email="info@nadireskills.com", address="Plot # 16, Fantom Mall, I-8 Markaz, Islamabad, 44790",
         services=["Public sector services", "Careers & opportunities", "Talent platform", "Partnerships"]),
    dict(code="NES-CONS", name="NES Consultancy", description="Study abroad admissions, visa processing, migration, "
         "tax filing and SECP company registration (Mandi Bahauddin).",
         website="https://consultant.nadireskills.com", phone="0345 2193466", whatsapp="+92 345 2193466",
         address="Ward No. 5, Mandi Bahauddin, Punjab",
         services=["University admissions", "Student visa & interview", "IELTS & PTE preparation", "Visa processing",
                   "Migration & overseas jobs", "Translation services", "NTN registration", "Annual tax return",
                   "Tax planning", "Company formation (SECP)", "Trademark registration", "Chamber of Commerce",
                   "File preparation", "Embassy appointment booking"]),
    dict(code="NES-ACAD", name="Nadir Academy", description="Practical training: digital marketing, graphic design, "
         "e-commerce, IT, Arduino, programming, IELTS/PTE.",
         website="https://academy.nadireskills.com", phone="+92 345 2193460", whatsapp="+92 345 2193460",
         email="academy@nadireskills.com", address="Ward No. 5, Mandi Bahauddin",
         services=["Graphic Designing", "E-Commerce", "Digital Marketing", "Basic IT Course", "Arduino",
                   "Programming", "IELTS", "PTE", "Store: hardware, software, books"]),
    dict(code="NES-DM", name="NES Digital Marketing", description="Digital marketing agency serving Pakistan and "
         "international markets.", website="https://nesdigitalmarketing.com", whatsapp="+92 333 8208609",
         email="digitalmarketingnes@gmail.com",
         services=["SEO", "Meta Ads", "Google Ads", "Social media marketing", "Website design & development",
                   "Lead generation", "Content marketing", "Conversion rate optimization", "Sales funnels",
                   "Digital marketing strategy"]),
    dict(code="NES-SERV", name="Nadir Services", description="Government documents, attestation, translation and "
         "admissions support.", website="https://nadireskills.com/services/",
         services=["Government documents", "Attestation", "Translation", "Admissions support", "Printing",
                   "Online applications", "Computer services"]),
    dict(code="NES-STUDIO", name="Nadir Studio", description="Logos, branding and printing.",
         services=["Logo & brand identity", "Printing", "Creative production"]),
    dict(code="NES-EVENTS", name="NES Events", description="Published on nadireskills.com as 'Nadir Expo & Events': "
         "study abroad expos, seminars and business events.",
         services=["Study abroad expos & educational fairs", "Business & trade exhibitions", "Seminars & workshops",
                   "Sponsorship & partnership coordination"]),
    dict(code="NES-ECOM", name="NES E-commerce", description="Group e-commerce ventures. Details to be confirmed by the CEO.",
         services=[]),
]

# company code -> [(dept code, name, group_wide)]
DEPARTMENTS = {
    "NES-GROUP": [("EXEC", "Executive Office", True), ("HR", "Human Resources", True), ("FIN", "Finance", True),
                  ("OPS", "Operations", True), ("IT", "Information Technology", True),
                  ("LEGAL", "Legal & Compliance", True)],
    "NES-CONS": [("SALES", "Sales & Client Services", False), ("STUDY", "Study Abroad & Admissions", False),
                 ("VISA", "Visa, Migration & Jobs", False), ("APPT", "Embassy Appointment Booking", False),
                 ("TAX", "Business & Tax Services", False), ("OPSQA", "Operations & Quality", False)],
    "NES-ACAD": [("SALES", "Sales and Admissions", False), ("ACADEMIC", "Academic Management", False),
                 ("ADMIN", "Administration", False), ("EXAM", "Examination", False)],
    "NES-DM": [("SALES", "Sales", False), ("CREATIVE", "Creative", False), ("DEV", "Development", False),
               ("ECOM", "E-commerce", False)],
    "NES-SERV": [("DESK", "Service Desk", False)],
    "NES-STUDIO": [("CREATIVE", "Creative & Production", False)],
    "NES-EVENTS": [("EVENTS", "Events & Expos", False)],
    "NES-ECOM": [("OPS", "E-commerce Operations", False)],
}

PIPELINES = {
    "NES-GROUP": ["Inquiry", "Routed to team", "In discussion"],
    "NES-CONS": ["Inquiry", "Needs Assessment", "Evaluate & Prepare", "Submit & Track", "Welcome / Next Steps"],
    "NES-ACAD": ["Inquiry", "Counselling", "Admission Form", "Fee Pending", "Enrolled"],
    "NES-DM": ["Inquiry", "Free Consultation", "Proposal Sent", "Negotiation", "Onboarding"],
    "NES-SERV": ["Request", "Documents Received", "In Process", "Ready for Collection"],
    "NES-STUDIO": ["Order", "Design", "Client Approval", "Production", "Ready"],
    "NES-EVENTS": ["Inquiry", "Proposal", "Confirmed", "Executed"],
    "NES-ECOM": ["Inquiry", "Quote", "Order Placed"],
}

# permission presets
RES = ["research", "data_analysis", "internal_report"]
DRAFT = ["draft_document"]
CRM = ["crm_update"]
COORD = ["task_recommend", "internal_report", "data_analysis"]
MSG = ["customer_message", "send_external_email"]

# (company, dept, name, tier, perms, responsibilities)
A = [
    # ---- Group executive
    ("NES-GROUP", "EXEC", "Executive Assistant", OPUS, COORD + RES + DRAFT,
     ["Daily CEO briefing, weekly report and monthly review from system data",
      "Answer the CEO's questions across all companies using verified data",
      "Prepare management meetings, decision summaries and approval queues",
      "Strategic recommendations, hiring and expansion analyses"]),
    # ---- NES Consultancy
    ("NES-CONS", "SALES", "Sales Director Agent", OPUS, COORD + RES + CRM, ["Pipeline review and sales targets", "Coach sales staff with weekly insights"]),
    ("NES-CONS", "SALES", "Lead Generation Agent", SONNET, RES + DRAFT + CRM, ["Identify lead sources (expos, referrals, campaigns)", "Draft outreach for approval"]),
    ("NES-CONS", "SALES", "Lead Qualification Agent", HAIKU, ["data_analysis"] + CRM, ["Classify inquiries by service", "Score and route leads to the right desk"]),
    ("NES-CONS", "SALES", "Customer Support Agent", HAIKU, DRAFT + CRM + ["customer_message"], ["Draft replies to WhatsApp/email inquiries", "Escalate sensitive cases to humans"]),
    ("NES-CONS", "SALES", "Client Follow-up Agent", HAIKU, DRAFT + CRM + ["customer_message"], ["Track follow-up dates", "Draft follow-up messages for approval"]),
    ("NES-CONS", "STUDY", "Study Abroad Research Agent", SONNET, RES + DRAFT, ["Country requirements for UK, USA, Canada, Australia, Cyprus, France, New Zealand, Italy and others", "Cost-of-study comparisons"]),
    ("NES-CONS", "STUDY", "University Research Agent", SONNET, RES + DRAFT, ["Shortlist universities to the student's grades, budget and goals", "Track intakes and deadlines"]),
    ("NES-CONS", "STUDY", "Scholarship Agent", SONNET, RES + DRAFT, ["Find scholarships matching student profiles", "Track scholarship deadlines"]),
    ("NES-CONS", "STUDY", "Admission Processing Agent", SONNET, DRAFT + CRM + ["submit_application"], ["Prepare application checklists and SOP drafts", "Prepare submissions for human approval"]),
    ("NES-CONS", "VISA", "Visa Research Agent", SONNET, RES + DRAFT, ["Visa requirements, financial evidence rules and interview preparation material"]),
    ("NES-CONS", "VISA", "Document Verification Assistant", SONNET, ["data_analysis", "internal_report"], ["Check client files for missing or inconsistent documents before submission"]),
    ("NES-CONS", "VISA", "International Jobs Research Agent", SONNET, RES, ["Research overseas job openings and legal migration routes"]),
    ("NES-CONS", "VISA", "Employer Verification Agent", SONNET, RES, ["Verify overseas employers and flag fraud risk"]),
    ("NES-CONS", "VISA", "CV Preparation Agent", SONNET, DRAFT, ["Draft CVs and cover letters for client review"]),
    ("NES-CONS", "VISA", "Recruitment Coordination Agent", HAIKU, COORD + CRM, ["Track candidate applications and interview schedules"]),
    ("NES-CONS", "VISA", "Travel Research Agent", HAIKU, RES, ["Research routes, fares and travel requirements"]),
    ("NES-CONS", "VISA", "Ticketing Assistant", HAIKU, DRAFT + ["financial_commitment"], ["Prepare ticket options for approval (no purchases without approval)"]),
    ("NES-CONS", "APPT", "Embassy Appointment Agent", SONNET, RES + DRAFT + CRM, ["Track appointment slots and case timelines", "Prepare required-document lists per embassy"]),
    ("NES-CONS", "OPSQA", "Consultancy Operations Agent", SONNET, COORD, ["Monitor case progress across desks", "Flag stuck files"]),
    ("NES-CONS", "OPSQA", "Quality Assurance Agent", SONNET, ["data_analysis", "internal_report"], ["Review completed files against checklists", "Report recurring errors"]),
    ("NES-CONS", "TAX", "Tax & SECP Services Agent", SONNET, RES + DRAFT, ["Prepare NTN, tax return, SECP and trademark document checklists", "Track filing deadlines"]),
    # ---- Nadir Academy
    ("NES-ACAD", "SALES", "Education Sales Agent", SONNET, RES + CRM + DRAFT, ["Course inquiries pipeline", "Seasonal campaign ideas"]),
    ("NES-ACAD", "SALES", "Student Admission Agent", HAIKU, CRM + DRAFT, ["Admission forms and fee status tracking"]),
    ("NES-ACAD", "SALES", "Course Recommendation Agent", HAIKU, ["data_analysis"] + DRAFT, ["Recommend courses to the student's goals and level"]),
    ("NES-ACAD", "ACADEMIC", "Academic Coordinator Agent", SONNET, COORD, ["Batch planning and teacher coordination"]),
    ("NES-ACAD", "ACADEMIC", "Lesson Planning Agent", SONNET, DRAFT + ["research"], ["Draft lesson plans for teacher review"]),
    ("NES-ACAD", "ACADEMIC", "Student Progress Agent", HAIKU, ["data_analysis", "internal_report"], ["Track progress and flag at-risk students"]),
    ("NES-ACAD", "ADMIN", "Attendance Agent (Students)", HAIKU, ["data_analysis", "internal_report"], ["Student attendance summaries"]),
    ("NES-ACAD", "ADMIN", "Fee Management Agent", HAIKU, ["data_analysis", "internal_report"] + ["customer_message"], ["Fee due lists and reminder drafts"]),
    ("NES-ACAD", "ADMIN", "Timetable Agent", HAIKU, ["task_recommend", "internal_report"], ["Draft class timetables without clashes"]),
    ("NES-ACAD", "EXAM", "Examination Scheduling Agent", HAIKU, ["task_recommend", "internal_report"], ["Exam schedules and invigilation plans"]),
    ("NES-ACAD", "EXAM", "Question Preparation Assistant", SONNET, DRAFT, ["Draft question papers for teacher approval"]),
    ("NES-ACAD", "EXAM", "Result Processing Agent", HAIKU, ["data_analysis", "internal_report"], ["Compile results for verification"]),
    ("NES-ACAD", "EXAM", "Certificate Coordination Agent", HAIKU, DRAFT + ["publish_content"], ["Prepare certificate lists for approval"]),
    # ---- NES Digital Marketing
    ("NES-DM", "SALES", "Lead Generation Agent", SONNET, RES + DRAFT + CRM, ["Find prospects locally and internationally", "Draft outreach for approval"]),
    ("NES-DM", "SALES", "Sales Agent", SONNET, CRM + DRAFT + ["customer_message"], ["Qualify prospects and book free consultations"]),
    ("NES-DM", "SALES", "Proposal Agent", SONNET, DRAFT + ["discount"], ["Draft proposals with fixed fees for approval"]),
    ("NES-DM", "SALES", "Marketing Strategist", OPUS, RES + DRAFT, ["Audits, competitor research and 90-day roadmaps"]),
    ("NES-DM", "SALES", "Customer Support Agent", HAIKU, DRAFT + CRM + ["customer_message"], ["Client questions and monthly report delivery drafts"]),
    ("NES-DM", "CREATIVE", "Creative Director Agent", SONNET, COORD + DRAFT, ["Creative briefs and review of creative output"]),
    ("NES-DM", "CREATIVE", "SEO Agent", SONNET, RES + DRAFT, ["Technical, on-page and local SEO tasks"]),
    ("NES-DM", "CREATIVE", "Social Media Agent", SONNET, DRAFT + ["publish_content"], ["Content calendars and post drafts for approval"]),
    ("NES-DM", "CREATIVE", "Graphic Design Assistant", HAIKU, DRAFT, ["Design briefs and copy for designers"]),
    ("NES-DM", "CREATIVE", "Video Production Coordinator", HAIKU, ["task_recommend"] + DRAFT, ["Video scripts and editing schedules"]),
    ("NES-DM", "DEV", "Project Manager Agent", SONNET, COORD, ["Client project timelines, milestones and status reports"]),
    ("NES-DM", "DEV", "Web Development Assistant", OPUS, DRAFT + ["research"], ["WordPress/Elementor builds, fixes and specs"]),
    ("NES-DM", "DEV", "Software Development Assistant", OPUS, DRAFT + ["research"], ["Code drafts and technical specs for developer review"]),
    ("NES-DM", "DEV", "QA Agent", SONNET, ["data_analysis", "internal_report"], ["Test plans and pre-launch checklists"]),
    ("NES-DM", "ECOM", "Product Research Agent", SONNET, RES, ["Product and market research for e-commerce clients"]),
    ("NES-DM", "ECOM", "E-commerce Operations Agent", SONNET, COORD + DRAFT, ["Store setup and catalogue tasks"]),
    # ---- Nadir Services
    ("NES-SERV", "DESK", "Customer Support Agent", HAIKU, DRAFT + CRM + ["customer_message"], ["Answer service inquiries and required-document questions"]),
    ("NES-SERV", "DESK", "Printing Services Agent", HAIKU, DRAFT + CRM, ["Printing order intake and status"]),
    ("NES-SERV", "DESK", "Online Application Assistant", SONNET, DRAFT + ["submit_application"], ["Prepare online applications for approval"]),
    ("NES-SERV", "DESK", "Computer Services Agent", HAIKU, DRAFT, ["Computer service requests"]),
    ("NES-SERV", "DESK", "Order Management Agent", HAIKU, CRM + ["internal_report"], ["Track orders from request to collection"]),
    ("NES-SERV", "DESK", "Daily Cash Reporting Agent", HAIKU, ["data_analysis", "internal_report"], ["Daily cash summary from recorded entries"]),
    # ---- Nadir Studio
    ("NES-STUDIO", "CREATIVE", "Creative Order Agent", HAIKU, CRM + DRAFT, ["Order intake and briefs"]),
    ("NES-STUDIO", "CREATIVE", "Design Coordination Agent", HAIKU, ["task_recommend"] + DRAFT, ["Assign design work and track approvals"]),
    ("NES-STUDIO", "CREATIVE", "Printing Production Agent", HAIKU, ["task_recommend", "internal_report"], ["Production queue and delivery dates"]),
    ("NES-STUDIO", "CREATIVE", "Translation Coordination Agent", HAIKU, ["task_recommend"] + DRAFT, ["Translation jobs and proofreading"]),
    ("NES-STUDIO", "CREATIVE", "Quality Control Agent", HAIKU, ["data_analysis", "internal_report"], ["Check outputs against the order"]),
    ("NES-STUDIO", "CREATIVE", "Customer Follow-up Agent", HAIKU, DRAFT + ["customer_message"], ["Ready/collection notifications for approval"]),
    # ---- Events & E-commerce (added: each department needs coverage)
    ("NES-EVENTS", "EVENTS", "Events Planning Agent", SONNET, RES + DRAFT, ["Expo and seminar plans, vendor lists, timelines"]),
    ("NES-EVENTS", "EVENTS", "Sponsorship & Partnership Agent", SONNET, RES + DRAFT + CRM, ["Sponsor prospect lists and proposals for approval"]),
    ("NES-ECOM", "OPS", "Store Operations Agent", SONNET, COORD + DRAFT, ["Catalogue, orders and fulfilment tracking"]),
    # ---- Group-wide: HR
    ("NES-GROUP", "HR", "Recruitment Agent", SONNET, RES + DRAFT + ["hiring"], ["Job descriptions, CV screening summaries"]),
    ("NES-GROUP", "HR", "Training Agent", SONNET, DRAFT + ["task_recommend"], ["Training plans per skill level"]),
    ("NES-GROUP", "HR", "Attendance Agent (Staff)", HAIKU, ["data_analysis", "internal_report"], ["Staff attendance summaries"]),
    ("NES-GROUP", "HR", "Employee Performance Agent", SONNET, ["data_analysis", "internal_report"], ["Performance summaries using quality, impact and deadlines"]),
    ("NES-GROUP", "HR", "Onboarding Agent", HAIKU, DRAFT + ["task_recommend"], ["Onboarding checklists and first-week plans"]),
    ("NES-GROUP", "HR", "Workforce Planning Agent", SONNET, COORD, ["Capacity analysis and hiring plans"]),
    ("NES-GROUP", "HR", "Employee Help Desk", HAIKU, ["research", "internal_report"],
     ["Answer employees' questions in the NES Team app from their own HR data and published company policies",
      "Point employees to the right policy document or to HR when the answer isn't documented"]),
    # ---- Finance
    ("NES-GROUP", "FIN", "Finance Assistant", SONNET, ["data_analysis", "internal_report"], ["Answer finance questions from recorded data"]),
    ("NES-GROUP", "FIN", "Invoice Agent", HAIKU, DRAFT, ["Draft invoices for approval"]),
    ("NES-GROUP", "FIN", "Expense Analysis Agent", SONNET, ["data_analysis", "internal_report"], ["Expense trends and anomalies"]),
    ("NES-GROUP", "FIN", "Budget Monitoring Agent", HAIKU, ["data_analysis", "internal_report"], ["Budget vs actual alerts"]),
    ("NES-GROUP", "FIN", "Receivables Agent", HAIKU, ["data_analysis", "internal_report"] + ["customer_message"], ["Overdue invoice lists and reminder drafts"]),
    ("NES-GROUP", "FIN", "Financial Reporting Agent", SONNET, ["data_analysis", "internal_report"], ["Monthly company-wise P&L"]),
    # ---- Operations
    ("NES-GROUP", "OPS", "Operations Director Agent", OPUS, COORD, ["Cross-company operational review"]),
    ("NES-GROUP", "OPS", "SOP Management Agent", SONNET, DRAFT, ["Draft and maintain SOPs"]),
    ("NES-GROUP", "OPS", "Task Monitoring Agent", HAIKU, COORD, ["Overdue and blocked task monitoring"]),
    ("NES-GROUP", "OPS", "Workflow Automation Agent", SONNET, ["research", "internal_report"], ["Identify automation opportunities (n8n / Apps Script)"]),
    ("NES-GROUP", "OPS", "Quality Assurance Agent", SONNET, ["data_analysis", "internal_report"], ["Group-wide quality reviews"]),
    # ---- IT
    ("NES-GROUP", "IT", "IT Support Agent", HAIKU, DRAFT, ["Staff IT help and troubleshooting guides"]),
    ("NES-GROUP", "IT", "Infrastructure Monitoring Agent", HAIKU, ["data_analysis", "internal_report"], ["Server health summaries"]),
    ("NES-GROUP", "IT", "Database Monitoring Agent", HAIKU, ["data_analysis", "internal_report"], ["Database and backup checks"]),
    ("NES-GROUP", "IT", "Integration Monitoring Agent", HAIKU, ["data_analysis", "internal_report"], ["Integration status checks"]),
    ("NES-GROUP", "IT", "Cybersecurity Monitoring Agent", SONNET, ["data_analysis", "internal_report"], ["Audit-log review for suspicious activity"]),
    # ---- Legal
    ("NES-GROUP", "LEGAL", "Contract Review Assistant", OPUS, ["research", "internal_report"] + DRAFT, ["Flag risky clauses for human legal review"]),
    ("NES-GROUP", "LEGAL", "Compliance Research Agent", SONNET, RES, ["FBR, SECP and data-protection compliance research"]),
    ("NES-GROUP", "LEGAL", "Policy Management Agent", SONNET, DRAFT, ["Draft and version internal policies"]),
]


def instructions_for(name: str, resp: list[str]) -> str:
    return (f"Act as the {name}. Work only on your responsibilities: {'; '.join(resp)}. "
            "Base every statement on provided system data or approved knowledge. Draft, recommend and analyse; "
            "request approval for anything external. Escalate to your human supervisor when unsure.")


def seed(db: Session) -> dict:
    created = {"companies": 0, "departments": 0, "agents": 0, "pipelines": 0, "integrations": 0}
    comps: dict[str, m.Company] = {c.code: c for c in db.scalars(select(m.Company))}
    for c in COMPANIES:
        if c["code"] not in comps:
            obj = m.Company(**c)
            db.add(obj)
            db.flush()
            comps[c["code"]] = obj
            created["companies"] += 1
    parent = comps["NES-GROUP"]
    for code, c in comps.items():
        if code != "NES-GROUP" and not c.parent_id:
            c.parent_id = parent.id

    depts: dict[tuple[str, str], m.Department] = {}
    for ccode, items in DEPARTMENTS.items():
        comp = comps[ccode]
        for dcode, name, gw in items:
            d = db.scalar(select(m.Department).where(m.Department.company_id == comp.id, m.Department.code == dcode))
            if not d:
                d = m.Department(company_id=comp.id, code=dcode, name=name, is_group_wide=gw)
                db.add(d)
                db.flush()
                created["departments"] += 1
            depts[(ccode, dcode)] = d

    for ccode, stages in PIPELINES.items():
        if not db.scalar(select(m.Pipeline).where(m.Pipeline.company_id == comps[ccode].id)):
            db.add(m.Pipeline(company_id=comps[ccode].id, name="Sales", stages=stages))
            created["pipelines"] += 1

    ea = db.scalar(select(m.Agent).where(m.Agent.code == EXEC_CODE))
    inherit = ea if ea and ea.provider != "anthropic" else None

    def add_agent(code, ccode, dcode, name, model, perms, resp, coordinator=False, designation=None):
        if db.scalar(select(m.Agent).where(m.Agent.code == code)):
            return
        fall = [] if model == HAIKU else [{"provider": "anthropic", "model": SONNET if model == OPUS else HAIKU}]
        provider = "anthropic"
        if inherit:
            provider, model, fall = inherit.provider, inherit.model, []
        db.add(m.Agent(code=code, name=name, company_id=comps[ccode].id,
                       department_id=depts[(ccode, dcode)].id if dcode else None,
                       designation=designation or name.replace(" Agent", "").replace(" Assistant", " Assistant"),
                       job_description=resp[0], responsibilities=resp, instructions=instructions_for(name, resp),
                       provider=provider, model=model, fallbacks=fall, permissions=sorted(set(perms)),
                       tools=["tasks_read", "reports_read"] + (["crm_read"] if "crm_update" in perms else []),
                       is_coordinator=coordinator, status="configured",
                       daily_token_limit=200_000 if model == OPUS else 100_000))
        created["agents"] += 1

    for ccode, dcode, name, model, perms, resp in A:
        code = EXEC_CODE if name == "Executive Assistant" else \
            f"{ccode}-{dcode}-" + "".join(ch if ch.isalnum() else "-" for ch in name.upper()).strip("-")
        add_agent(code[:60], ccode, dcode, name, model, perms, resp,
                  designation="CEO Executive Assistant (Chief of Staff)" if name == "Executive Assistant" else None)
    # one AI coordinator per department
    for (ccode, dcode), d in depts.items():
        if (ccode, dcode) == ("NES-GROUP", "EXEC"):
            continue
        add_agent(f"{ccode}-{dcode}-COORDINATOR"[:60], ccode, dcode, f"{d.name} Coordinator", SONNET, COORD,
                  [f"Coordinate the {d.name} department's people and agents",
                   "Morning priorities, task recommendations and end-of-day summary for the department head"],
                  coordinator=True, designation=f"AI Department Coordinator — {d.name}")
    db.flush()
    # coordinators supervise specialist agents
    for (ccode, dcode), d in depts.items():
        coord = db.scalar(select(m.Agent).where(m.Agent.department_id == d.id, m.Agent.is_coordinator.is_(True)))
        if coord:
            for a in db.scalars(select(m.Agent).where(m.Agent.department_id == d.id, m.Agent.is_coordinator.is_(False),
                                                      m.Agent.supervisor_agent_id.is_(None))):
                a.supervisor_agent_id = coord.id

    for key, name in INTEGRATIONS.items():
        if not db.get(m.Integration, key):
            db.add(m.Integration(key=key, name=name, status="NOT CONNECTED"))
            created["integrations"] += 1
    if not db.get(m.Setting, "daily_ops"):
        put_setting(db, "daily_ops", DAILY_OPS_DEFAULT)
    for p in ["anthropic", "openai", "gemini", "openai_compatible"]:
        if not db.get(m.AIProviderConfig, p):
            db.add(m.AIProviderConfig(provider=p))
    db.commit()
    return created
