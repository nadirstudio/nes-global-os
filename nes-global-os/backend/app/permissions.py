"""Role-based permissions, data scoping (multi-company isolation) and AI-agent action governance.

The matrix here is the single source of truth; docs/PERMISSIONS_MATRIX.md mirrors it.
"""
from __future__ import annotations

import uuid
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from . import models as m

ROLES = ["ceo", "director", "dept_head", "manager", "employee", "intern", "freelancer"]

ROLE_LABELS = {
    "ceo": "CEO", "director": "Director", "dept_head": "Department Head", "manager": "Manager",
    "employee": "Employee", "intern": "Intern", "freelancer": "Freelancer",
}

ALL = set(ROLES)
LEADERS = {"ceo", "director", "dept_head", "manager"}
SENIOR = {"ceo", "director", "dept_head"}

# action -> roles allowed (within their data scope)
MATRIX: dict[str, set[str]] = {
    "dashboard.view": LEADERS,
    "company.manage": {"ceo"},
    "department.manage": {"ceo", "director"},
    "people.view": LEADERS,
    "people.manage": {"ceo", "director", "dept_head"},
    "users.manage": {"ceo"},
    "agents.view": LEADERS,
    "agents.manage": {"ceo", "director", "dept_head"},
    "agents.run": {"ceo", "director", "dept_head", "manager"},
    "tasks.view": ALL,
    "tasks.create": LEADERS,
    "tasks.update_own": ALL,
    "tasks.review": LEADERS,
    "approvals.view": LEADERS,
    "approvals.decide": SENIOR,
    "crm.view": LEADERS | {"employee", "freelancer"},
    "crm.manage": LEADERS | {"employee"},
    "projects.view": ALL,
    "projects.manage": {"ceo", "director", "dept_head"},
    "finance.view": {"ceo", "director"},
    "finance.manage": {"ceo", "director"},
    "ai.settings": {"ceo"},
    "ai.usage.view": {"ceo", "director"},
    "integrations.view": {"ceo", "director"},
    "integrations.manage": {"ceo"},
    "audit.view": {"ceo"},
    "assistant.use": {"ceo", "director"},
    "reports.view": {"ceo"},  # group-wide reports span all companies
    "workforce.intelligence": LEADERS,
    "attendance.manage": LEADERS,
}


def can(role: str, action: str) -> bool:
    return role in MATRIX.get(action, set())


@dataclass
class Scope:
    """What slice of the organisation a user may see. None == unrestricted."""
    company_ids: set[uuid.UUID] | None
    department_ids: set[uuid.UUID] | None
    person_id: uuid.UUID | None
    own_only: bool  # employees / interns / freelancers see only their own work

    def allows_company(self, cid: uuid.UUID | None) -> bool:
        return self.company_ids is None or (cid is not None and cid in self.company_ids)

    def allows_department(self, did: uuid.UUID | None, cid: uuid.UUID | None = None) -> bool:
        if not self.allows_company(cid) and cid is not None:
            return False
        return self.department_ids is None or (did is not None and did in self.department_ids)


def scope_for(db: Session, user: m.User) -> Scope:
    if user.role == "ceo":
        return Scope(None, None, user.person_id, False)
    person = db.get(m.Person, user.person_id) if user.person_id else None
    companies: set[uuid.UUID] = set()
    if person and person.company_id:
        companies.add(person.company_id)
    extra = db.scalars(select(m.UserCompanyAccess.company_id).where(m.UserCompanyAccess.user_id == user.id))
    companies.update(extra)
    if user.role == "director":
        return Scope(companies, None, user.person_id, False)
    if user.role in {"dept_head", "manager"}:
        depts: set[uuid.UUID] = set()
        if person and person.department_id:
            depts.add(person.department_id)
        if person:
            depts.update(db.scalars(select(m.Department.id).where(m.Department.head_person_id == person.id)))
        return Scope(companies, depts, user.person_id, False)
    return Scope(companies, set(), user.person_id, True)


# ---------------------------------------------------------------- AI agent governance
AGENT_AUTOMATIC = {
    "research": "Research using approved sources",
    "internal_report": "Prepare internal reports",
    "draft_document": "Draft documents for human review",
    "crm_update": "Authorized CRM updates (notes, scores, stage suggestions)",
    "task_recommend": "Recommend task assignments",
    "data_analysis": "Analyse internal data",
}
AGENT_NEEDS_APPROVAL = {
    "send_external_email": "Send external email",
    "customer_message": "Send customer communication (WhatsApp/SMS)",
    "submit_application": "Submit university / job applications",
    "submit_visa": "Submit visa applications",
    "publish_content": "Publish content",
    "contract": "Contracts",
    "financial_commitment": "Financial commitments",
    "hiring": "Hiring decisions",
    "salary_change": "Salary changes",
    "discount": "Discounts",
    "sensitive_customer_decision": "Sensitive customer decisions",
}
AGENT_PROHIBITED = {
    "payment": "Payments / bank transfers",
    "delete_records": "Deleting records",
    "disclose_confidential": "Disclosing confidential data",
    "change_bank_details": "Changing bank details",
    "legal_commitment": "Legal commitments",
}


def agent_action_policy(agent: m.Agent, action: str) -> str:
    """Returns 'allow', 'approval' or 'deny'. Prohibited actions are never grantable."""
    if action in AGENT_PROHIBITED:
        return "deny"
    if action not in (agent.permissions or []):
        return "deny"
    if action in AGENT_NEEDS_APPROVAL:
        return "approval"
    if action in AGENT_AUTOMATIC:
        return "allow"
    return "deny"


def sanitize_agent_permissions(perms: list[str]) -> list[str]:
    allowed = set(AGENT_AUTOMATIC) | set(AGENT_NEEDS_APPROVAL)
    return sorted({p for p in perms if p in allowed})
