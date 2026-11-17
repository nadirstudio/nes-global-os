"""NES GLOBAL OS data model — PostgreSQL is the single system of record.

UUID primary keys are used everywhere so records created on the local office server
and in the cloud can be merged without ID collisions.
"""
from __future__ import annotations

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal

from sqlalchemy import (
    JSON, Boolean, Date, DateTime, ForeignKey, Integer, Numeric, String, Text,
    UniqueConstraint, Index,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def pk() -> Mapped[uuid.UUID]:
    return mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)


def fk(target: str, nullable: bool = True, ondelete: str = "SET NULL") -> Mapped:
    return mapped_column(UUID(as_uuid=True), ForeignKey(target, ondelete=ondelete), nullable=nullable, index=True)


class Timestamped:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


# ---------------------------------------------------------------- organisation
class Company(Timestamped, Base):
    __tablename__ = "companies"
    id: Mapped[uuid.UUID] = pk()
    code: Mapped[str] = mapped_column(String(32), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="unit")  # parent | unit | venture
    parent_id: Mapped[uuid.UUID | None] = fk("companies.id")
    description: Mapped[str | None] = mapped_column(Text)
    website: Mapped[str | None] = mapped_column(String(300))
    phone: Mapped[str | None] = mapped_column(String(60))
    whatsapp: Mapped[str | None] = mapped_column(String(60))
    email: Mapped[str | None] = mapped_column(String(200))
    address: Mapped[str | None] = mapped_column(Text)
    services: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | planned | paused
    departments: Mapped[list[Department]] = relationship(back_populates="company")


class Department(Timestamped, Base):
    __tablename__ = "departments"
    __table_args__ = (UniqueConstraint("company_id", "code"),)
    id: Mapped[uuid.UUID] = pk()
    company_id: Mapped[uuid.UUID] = fk("companies.id", nullable=False, ondelete="CASCADE")
    code: Mapped[str] = mapped_column(String(40))
    name: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    is_group_wide: Mapped[bool] = mapped_column(Boolean, default=False)
    head_person_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("people.id", ondelete="SET NULL", use_alter=True, name="fk_departments_head_person"),
        nullable=True, index=True)
    status: Mapped[str] = mapped_column(String(20), default="active")
    company: Mapped[Company] = relationship(back_populates="departments")


# ---------------------------------------------------------------- people & access
class Person(Timestamped, Base):
    __tablename__ = "people"
    id: Mapped[uuid.UUID] = pk()
    employee_code: Mapped[str] = mapped_column(String(32), unique=True)
    full_name: Mapped[str] = mapped_column(String(200))
    email: Mapped[str | None] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(60))
    category: Mapped[str] = mapped_column(String(40), default="permanent")
    designation: Mapped[str | None] = mapped_column(String(200))
    company_id: Mapped[uuid.UUID | None] = fk("companies.id")
    department_id: Mapped[uuid.UUID | None] = fk("departments.id")
    manager_id: Mapped[uuid.UUID | None] = fk("people.id")
    skill_level: Mapped[str] = mapped_column(String(20), default="beginner")
    skills: Mapped[list] = mapped_column(JSON, default=list)
    experience_years: Mapped[Decimal] = mapped_column(Numeric(4, 1), default=0)
    weekly_capacity_hours: Mapped[Decimal] = mapped_column(Numeric(5, 1), default=48)
    responsibilities: Mapped[str | None] = mapped_column(Text)
    training_requirements: Mapped[list] = mapped_column(JSON, default=list)
    training_completed: Mapped[list] = mapped_column(JSON, default=list)
    achievements: Mapped[list] = mapped_column(JSON, default=list)
    joined_on: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(20), default="active")  # active | onboarding | inactive


class User(Timestamped, Base):
    __tablename__ = "users"
    id: Mapped[uuid.UUID] = pk()
    email: Mapped[str] = mapped_column(String(200), unique=True)
    password_hash: Mapped[str] = mapped_column(String(200))
    role: Mapped[str] = mapped_column(String(20))
    person_id: Mapped[uuid.UUID | None] = fk("people.id")
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    mfa_secret_enc: Mapped[str | None] = mapped_column(Text)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    failed_logins: Mapped[int] = mapped_column(Integer, default=0)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_login_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    token_version: Mapped[int] = mapped_column(Integer, default=0)
    person: Mapped[Person | None] = relationship()


class UserCompanyAccess(Base):
    """Extra companies a director / freelancer may see beyond their own."""
    __tablename__ = "user_company_access"
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    company_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)


class Attendance(Base):
    __tablename__ = "attendance"
    __table_args__ = (UniqueConstraint("person_id", "day"),)
    id: Mapped[uuid.UUID] = pk()
    person_id: Mapped[uuid.UUID] = fk("people.id", nullable=False, ondelete="CASCADE")
    day: Mapped[date] = mapped_column(Date, index=True)
    check_in: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    check_out: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="present")  # present | late | leave | absent | remote
    note: Mapped[str | None] = mapped_column(Text)
    # mobile check-in evidence
    method: Mapped[str | None] = mapped_column(String(20))  # web | mobile | manual
    site_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    in_lat: Mapped[float | None] = mapped_column(Numeric(10, 7))
    in_lng: Mapped[float | None] = mapped_column(Numeric(10, 7))
    in_accuracy_m: Mapped[float | None] = mapped_column(Numeric(8, 1))
    in_distance_m: Mapped[float | None] = mapped_column(Numeric(10, 1))
    out_lat: Mapped[float | None] = mapped_column(Numeric(10, 7))
    out_lng: Mapped[float | None] = mapped_column(Numeric(10, 7))
    outside_geofence: Mapped[bool] = mapped_column(Boolean, default=False)
    biometric_confirmed: Mapped[bool] = mapped_column(Boolean, default=False)
    device_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    field_approved: Mapped[bool | None] = mapped_column(Boolean)  # for outside-geofence check-ins


# ---------------------------------------------------------------- AI workforce
class Agent(Timestamped, Base):
    __tablename__ = "agents"
    id: Mapped[uuid.UUID] = pk()
    code: Mapped[str] = mapped_column(String(60), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    company_id: Mapped[uuid.UUID] = fk("companies.id", nullable=False, ondelete="CASCADE")
    department_id: Mapped[uuid.UUID | None] = fk("departments.id")
    designation: Mapped[str | None] = mapped_column(String(200))
    job_description: Mapped[str | None] = mapped_column(Text)
    responsibilities: Mapped[list] = mapped_column(JSON, default=list)
    instructions: Mapped[str | None] = mapped_column(Text)
    knowledge: Mapped[str | None] = mapped_column(Text)
    provider: Mapped[str] = mapped_column(String(30), default="anthropic")
    model: Mapped[str] = mapped_column(String(80), default="claude-sonnet-5-5")
    fallbacks: Mapped[list] = mapped_column(JSON, default=list)  # [{"provider":..,"model":..}]
    tools: Mapped[list] = mapped_column(JSON, default=list)
    permissions: Mapped[list] = mapped_column(JSON, default=list)
    supervisor_person_id: Mapped[uuid.UUID | None] = fk("people.id")
    supervisor_agent_id: Mapped[uuid.UUID | None] = fk("agents.id")
    is_coordinator: Mapped[bool] = mapped_column(Boolean, default=False)
    schedule: Mapped[list] = mapped_column(JSON, default=list)  # [{"at":"08:45","job":"..."}]
    status: Mapped[str] = mapped_column(String(20), default="draft")
    monthly_budget: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    daily_token_limit: Mapped[int | None] = mapped_column(Integer)
    version: Mapped[int] = mapped_column(Integer, default=1)
    last_tested_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_test_ok: Mapped[bool | None] = mapped_column(Boolean)


class AgentRun(Base):
    __tablename__ = "agent_runs"
    id: Mapped[uuid.UUID] = pk()
    agent_id: Mapped[uuid.UUID] = fk("agents.id", nullable=False, ondelete="CASCADE")
    task_id: Mapped[uuid.UUID | None] = fk("tasks.id")
    trigger: Mapped[str] = mapped_column(String(30))  # test | task | schedule | assistant
    input: Mapped[str | None] = mapped_column(Text)
    output: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20))  # succeeded | failed | blocked
    provider: Mapped[str | None] = mapped_column(String(30))
    model: Mapped[str | None] = mapped_column(String(80))
    input_tokens: Mapped[int] = mapped_column(Integer, default=0)
    output_tokens: Mapped[int] = mapped_column(Integer, default=0)
    cost: Mapped[Decimal] = mapped_column(Numeric(12, 6), default=0)
    cost_currency: Mapped[str] = mapped_column(String(8), default="USD")
    priced: Mapped[bool] = mapped_column(Boolean, default=False)
    error: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AIProviderConfig(Timestamped, Base):
    __tablename__ = "ai_providers"
    provider: Mapped[str] = mapped_column(String(30), primary_key=True)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    api_key_enc: Mapped[str | None] = mapped_column(Text)
    key_hint: Mapped[str | None] = mapped_column(String(12))
    base_url: Mapped[str | None] = mapped_column(String(300))
    status: Mapped[str] = mapped_column(String(30), default="NOT CONNECTED")
    last_error: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class ModelPrice(Base):
    """Per-model prices entered by the administrator (USD per million tokens)."""
    __tablename__ = "model_prices"
    model: Mapped[str] = mapped_column(String(80), primary_key=True)
    provider: Mapped[str] = mapped_column(String(30))
    input_per_mtok: Mapped[Decimal] = mapped_column(Numeric(10, 4))
    output_per_mtok: Mapped[Decimal] = mapped_column(Numeric(10, 4))


# ---------------------------------------------------------------- work
class Project(Timestamped, Base):
    __tablename__ = "projects"
    id: Mapped[uuid.UUID] = pk()
    company_id: Mapped[uuid.UUID] = fk("companies.id", nullable=False, ondelete="CASCADE")
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(40), default="internal")  # internal | client | venture | white_label
    manager_person_id: Mapped[uuid.UUID | None] = fk("people.id")
    objectives: Mapped[str | None] = mapped_column(Text)
    budget: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(8), default="PKR")
    status: Mapped[str] = mapped_column(String(20), default="planning")  # planning|active|on_hold|done|cancelled
    start_on: Mapped[date | None] = mapped_column(Date)
    deadline: Mapped[date | None] = mapped_column(Date)
    member_ids: Mapped[list] = mapped_column(JSON, default=list)
    agent_ids: Mapped[list] = mapped_column(JSON, default=list)


class Milestone(Base):
    __tablename__ = "milestones"
    id: Mapped[uuid.UUID] = pk()
    project_id: Mapped[uuid.UUID] = fk("projects.id", nullable=False, ondelete="CASCADE")
    title: Mapped[str] = mapped_column(String(200))
    deliverable: Mapped[str | None] = mapped_column(Text)
    due_on: Mapped[date | None] = mapped_column(Date)
    done: Mapped[bool] = mapped_column(Boolean, default=False)


class Task(Timestamped, Base):
    __tablename__ = "tasks"
    id: Mapped[uuid.UUID] = pk()
    company_id: Mapped[uuid.UUID] = fk("companies.id", nullable=False, ondelete="CASCADE")
    department_id: Mapped[uuid.UUID | None] = fk("departments.id")
    project_id: Mapped[uuid.UUID | None] = fk("projects.id")
    title: Mapped[str] = mapped_column(String(300))
    description: Mapped[str | None] = mapped_column(Text)
    assignee_person_id: Mapped[uuid.UUID | None] = fk("people.id")
    assignee_agent_id: Mapped[uuid.UUID | None] = fk("agents.id")
    reviewer_person_id: Mapped[uuid.UUID | None] = fk("people.id")
    created_by_user_id: Mapped[uuid.UUID | None] = fk("users.id")
    priority: Mapped[str] = mapped_column(String(10), default="medium")  # low|medium|high|urgent
    impact: Mapped[str] = mapped_column(String(10), default="medium")
    complexity: Mapped[str] = mapped_column(String(12), default="standard")  # basic|standard|complex
    required_skills: Mapped[list] = mapped_column(JSON, default=list)
    status: Mapped[str] = mapped_column(String(20), default="todo", index=True)
    due_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)
    estimated_hours: Mapped[Decimal] = mapped_column(Numeric(6, 1), default=1)
    quality_score: Mapped[int | None] = mapped_column(Integer)  # 1-5 set by reviewer
    customer_satisfaction: Mapped[int | None] = mapped_column(Integer)  # 1-5
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    result: Mapped[str | None] = mapped_column(Text)


class Approval(Timestamped, Base):
    __tablename__ = "approvals"
    id: Mapped[uuid.UUID] = pk()
    company_id: Mapped[uuid.UUID | None] = fk("companies.id")
    kind: Mapped[str] = mapped_column(String(40))
    title: Mapped[str] = mapped_column(String(300))
    payload: Mapped[dict] = mapped_column(JSON, default=dict)
    requested_by_user_id: Mapped[uuid.UUID | None] = fk("users.id")
    requested_by_agent_id: Mapped[uuid.UUID | None] = fk("agents.id")
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    decided_by_user_id: Mapped[uuid.UUID | None] = fk("users.id")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------- CRM
class Pipeline(Base):
    __tablename__ = "pipelines"
    id: Mapped[uuid.UUID] = pk()
    company_id: Mapped[uuid.UUID] = fk("companies.id", nullable=False, ondelete="CASCADE")
    name: Mapped[str] = mapped_column(String(120))
    stages: Mapped[list] = mapped_column(JSON, default=list)


class Customer(Timestamped, Base):
    __tablename__ = "customers"
    id: Mapped[uuid.UUID] = pk()
    company_id: Mapped[uuid.UUID] = fk("companies.id", nullable=False, ondelete="CASCADE")
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(60), index=True)
    email: Mapped[str | None] = mapped_column(String(200), index=True)
    city: Mapped[str | None] = mapped_column(String(100))
    notes: Mapped[str | None] = mapped_column(Text)


class Lead(Timestamped, Base):
    __tablename__ = "leads"
    id: Mapped[uuid.UUID] = pk()
    company_id: Mapped[uuid.UUID] = fk("companies.id", nullable=False, ondelete="CASCADE")
    pipeline_id: Mapped[uuid.UUID] = fk("pipelines.id", nullable=False, ondelete="CASCADE")
    stage: Mapped[str] = mapped_column(String(60))
    name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(60), index=True)
    email: Mapped[str | None] = mapped_column(String(200), index=True)
    source: Mapped[str | None] = mapped_column(String(60))
    service: Mapped[str | None] = mapped_column(String(200))
    score: Mapped[int] = mapped_column(Integer, default=0)
    value: Mapped[Decimal | None] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(8), default="PKR")
    owner_person_id: Mapped[uuid.UUID | None] = fk("people.id")
    customer_id: Mapped[uuid.UUID | None] = fk("customers.id")
    next_follow_up: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(20), default="open")  # open | won | lost
    notes: Mapped[str | None] = mapped_column(Text)


class Activity(Base):
    """Communication record / customer history entry."""
    __tablename__ = "activities"
    id: Mapped[uuid.UUID] = pk()
    company_id: Mapped[uuid.UUID] = fk("companies.id", nullable=False, ondelete="CASCADE")
    lead_id: Mapped[uuid.UUID | None] = fk("leads.id", ondelete="CASCADE")
    customer_id: Mapped[uuid.UUID | None] = fk("customers.id", ondelete="CASCADE")
    channel: Mapped[str] = mapped_column(String(20))  # call|whatsapp|email|visit|note
    direction: Mapped[str] = mapped_column(String(10), default="out")
    summary: Mapped[str] = mapped_column(Text)
    by_user_id: Mapped[uuid.UUID | None] = fk("users.id")
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


# ---------------------------------------------------------------- finance
class FinanceEntry(Timestamped, Base):
    __tablename__ = "finance_entries"
    id: Mapped[uuid.UUID] = pk()
    company_id: Mapped[uuid.UUID] = fk("companies.id", nullable=False, ondelete="CASCADE")
    project_id: Mapped[uuid.UUID | None] = fk("projects.id")
    kind: Mapped[str] = mapped_column(String(10))  # revenue | expense
    category: Mapped[str | None] = mapped_column(String(100))
    service: Mapped[str | None] = mapped_column(String(200))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    currency: Mapped[str] = mapped_column(String(8), default="PKR")
    fx_to_pkr: Mapped[Decimal] = mapped_column(Numeric(14, 6), default=1)
    description: Mapped[str | None] = mapped_column(Text)
    reference: Mapped[str | None] = mapped_column(String(100))
    occurred_on: Mapped[date] = mapped_column(Date, index=True)
    created_by_user_id: Mapped[uuid.UUID | None] = fk("users.id")


class Invoice(Timestamped, Base):
    __tablename__ = "invoices"
    __table_args__ = (UniqueConstraint("company_id", "number"),)
    id: Mapped[uuid.UUID] = pk()
    company_id: Mapped[uuid.UUID] = fk("companies.id", nullable=False, ondelete="CASCADE")
    customer_id: Mapped[uuid.UUID | None] = fk("customers.id")
    project_id: Mapped[uuid.UUID | None] = fk("projects.id")
    number: Mapped[str] = mapped_column(String(40))
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2))
    paid_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=0)
    currency: Mapped[str] = mapped_column(String(8), default="PKR")
    status: Mapped[str] = mapped_column(String(20), default="issued")  # draft|issued|partial|paid|void
    issued_on: Mapped[date | None] = mapped_column(Date)
    due_on: Mapped[date | None] = mapped_column(Date)
    description: Mapped[str | None] = mapped_column(Text)


# ---------------------------------------------------------------- system
class Integration(Timestamped, Base):
    __tablename__ = "integrations"
    key: Mapped[str] = mapped_column(String(40), primary_key=True)
    name: Mapped[str] = mapped_column(String(120))
    status: Mapped[str] = mapped_column(String(30), default="NOT CONNECTED")
    detail: Mapped[str | None] = mapped_column(Text)
    last_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class Setting(Base):
    __tablename__ = "settings"
    key: Mapped[str] = mapped_column(String(80), primary_key=True)
    value: Mapped[dict] = mapped_column(JSON)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)


class Report(Base):
    __tablename__ = "reports"
    id: Mapped[uuid.UUID] = pk()
    kind: Mapped[str] = mapped_column(String(30), index=True)
    company_id: Mapped[uuid.UUID | None] = fk("companies.id")
    period_start: Mapped[date] = mapped_column(Date)
    period_end: Mapped[date] = mapped_column(Date)
    content: Mapped[dict] = mapped_column(JSON)
    narrative: Mapped[str | None] = mapped_column(Text)
    narrative_source: Mapped[str] = mapped_column(String(30), default="data-only")
    generated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    generated_by: Mapped[str] = mapped_column(String(60), default="system")


class JobRun(Base):
    """Guarantees each scheduled job runs once per slot, even with several workers."""
    __tablename__ = "job_runs"
    __table_args__ = (UniqueConstraint("job", "slot"),)
    id: Mapped[uuid.UUID] = pk()
    job: Mapped[str] = mapped_column(String(60))
    slot: Mapped[str] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="running")
    detail: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class AuditLog(Base):
    __tablename__ = "audit_log"
    __table_args__ = (Index("ix_audit_at", "at"),)
    id: Mapped[uuid.UUID] = pk()
    at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    actor_user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_agent_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True))
    actor_label: Mapped[str | None] = mapped_column(String(200))
    action: Mapped[str] = mapped_column(String(60))
    entity: Mapped[str | None] = mapped_column(String(40))
    entity_id: Mapped[str | None] = mapped_column(String(60))
    company_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), index=True)
    detail: Mapped[dict] = mapped_column(JSON, default=dict)
    ip: Mapped[str | None] = mapped_column(String(60))


# ================================================================ employee app (release 1)
class WorkSite(Timestamped, Base):
    """Geofence: an office, branch or regular client site where check-in is allowed."""
    __tablename__ = "work_sites"
    id: Mapped[uuid.UUID] = pk()
    company_id: Mapped[uuid.UUID | None] = fk("companies.id")
    name: Mapped[str] = mapped_column(String(200))
    kind: Mapped[str] = mapped_column(String(20), default="office")  # office | branch | client
    lat: Mapped[float] = mapped_column(Numeric(10, 7))
    lng: Mapped[float] = mapped_column(Numeric(10, 7))
    radius_m: Mapped[int] = mapped_column(Integer, default=150)
    active: Mapped[bool] = mapped_column(Boolean, default=True)


class Device(Base):
    """A phone signed in to the employee app. Revoking it signs it out and wipes app data on next contact."""
    __tablename__ = "devices"
    id: Mapped[uuid.UUID] = pk()
    user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, ondelete="CASCADE")
    install_id: Mapped[str | None] = mapped_column(String(64), index=True)  # random id kept by the app install
    name: Mapped[str | None] = mapped_column(String(200))
    platform: Mapped[str | None] = mapped_column(String(40))
    app_version: Mapped[str | None] = mapped_column(String(20))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_ip: Mapped[str | None] = mapped_column(String(60))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    wipe: Mapped[bool] = mapped_column(Boolean, default=False)


class LeaveRequest(Timestamped, Base):
    __tablename__ = "leave_requests"
    id: Mapped[uuid.UUID] = pk()
    person_id: Mapped[uuid.UUID] = fk("people.id", nullable=False, ondelete="CASCADE")
    kind: Mapped[str] = mapped_column(String(20))  # annual | casual | sick | unpaid | overtime
    start_on: Mapped[date] = mapped_column(Date)
    end_on: Mapped[date] = mapped_column(Date)
    half_day: Mapped[bool] = mapped_column(Boolean, default=False)
    days: Mapped[Decimal] = mapped_column(Numeric(5, 1), default=0)
    hours: Mapped[Decimal | None] = mapped_column(Numeric(5, 1))  # overtime
    reason: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="pending", index=True)
    approver_person_id: Mapped[uuid.UUID | None] = fk("people.id")
    decided_by_user_id: Mapped[uuid.UUID | None] = fk("users.id")
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    decision_note: Mapped[str | None] = mapped_column(Text)


class Shift(Base):
    __tablename__ = "shifts"
    __table_args__ = (UniqueConstraint("person_id", "day"),)
    id: Mapped[uuid.UUID] = pk()
    person_id: Mapped[uuid.UUID] = fk("people.id", nullable=False, ondelete="CASCADE")
    day: Mapped[date] = mapped_column(Date, index=True)
    start_time: Mapped[str] = mapped_column(String(5))  # HH:MM
    end_time: Mapped[str] = mapped_column(String(5))
    site_id: Mapped[uuid.UUID | None] = fk("work_sites.id")
    note: Mapped[str | None] = mapped_column(String(200))


class Announcement(Base):
    __tablename__ = "announcements"
    id: Mapped[uuid.UUID] = pk()
    company_id: Mapped[uuid.UUID | None] = fk("companies.id", ondelete="CASCADE")  # None = whole group
    department_id: Mapped[uuid.UUID | None] = fk("departments.id", ondelete="CASCADE")
    title: Mapped[str] = mapped_column(String(200))
    body: Mapped[str] = mapped_column(Text)
    priority: Mapped[str] = mapped_column(String(10), default="normal")  # normal | urgent
    pinned: Mapped[bool] = mapped_column(Boolean, default=False)
    author_user_id: Mapped[uuid.UUID | None] = fk("users.id")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)


class AnnouncementRead(Base):
    __tablename__ = "announcement_reads"
    announcement_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("announcements.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChatChannel(Base):
    __tablename__ = "chat_channels"
    id: Mapped[uuid.UUID] = pk()
    kind: Mapped[str] = mapped_column(String(20))  # direct | department | company | group
    name: Mapped[str | None] = mapped_column(String(200))
    company_id: Mapped[uuid.UUID | None] = fk("companies.id", ondelete="CASCADE")
    department_id: Mapped[uuid.UUID | None] = fk("departments.id", ondelete="CASCADE")
    direct_key: Mapped[str | None] = mapped_column(String(80), unique=True)  # sorted user ids for DMs
    created_by_user_id: Mapped[uuid.UUID | None] = fk("users.id")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_message_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), index=True)


class ChatMember(Base):
    """Explicit membership (direct + group). Department/company channels derive membership from org data."""
    __tablename__ = "chat_members"
    channel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_channels.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)


class ChatRead(Base):
    __tablename__ = "chat_reads"
    channel_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("chat_channels.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True)
    last_read_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class ChatMessage(Base):
    __tablename__ = "chat_messages"
    __table_args__ = (Index("ix_chat_msg_channel_at", "channel_id", "created_at"),)
    id: Mapped[uuid.UUID] = pk()
    channel_id: Mapped[uuid.UUID] = fk("chat_channels.id", nullable=False, ondelete="CASCADE")
    sender_user_id: Mapped[uuid.UUID | None] = fk("users.id")
    body_enc: Mapped[str] = mapped_column(Text)  # encrypted at rest (Fernet)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    deleted: Mapped[bool] = mapped_column(Boolean, default=False)


class Document(Timestamped, Base):
    __tablename__ = "documents"
    id: Mapped[uuid.UUID] = pk()
    title: Mapped[str] = mapped_column(String(300))
    category: Mapped[str] = mapped_column(String(20))  # policy | sop | handbook | training | contract | form
    company_id: Mapped[uuid.UUID | None] = fk("companies.id", ondelete="CASCADE")
    department_id: Mapped[uuid.UUID | None] = fk("departments.id", ondelete="CASCADE")
    person_id: Mapped[uuid.UUID | None] = fk("people.id", ondelete="CASCADE")  # personal document (e.g. own contract)
    leaders_only: Mapped[bool] = mapped_column(Boolean, default=False)
    body_text: Mapped[str | None] = mapped_column(Text)  # searchable text; also the AI help desk's knowledge
    file_name: Mapped[str | None] = mapped_column(String(300))
    file_path: Mapped[str | None] = mapped_column(String(500))
    mime: Mapped[str | None] = mapped_column(String(100))
    size_bytes: Mapped[int | None] = mapped_column(Integer)
    sha256: Mapped[str | None] = mapped_column(String(64))
    version: Mapped[int] = mapped_column(Integer, default=1)
    uploaded_by_user_id: Mapped[uuid.UUID | None] = fk("users.id")


# ================================================================ calls (release 1.2)
class Call(Base):
    __tablename__ = "calls"
    id: Mapped[uuid.UUID] = pk()
    kind: Mapped[str] = mapped_column(String(10))  # direct | group
    media: Mapped[str] = mapped_column(String(10), default="audio")  # audio | video
    channel_id: Mapped[uuid.UUID | None] = fk("chat_channels.id")  # group call started from a chat group
    initiator_user_id: Mapped[uuid.UUID] = fk("users.id", nullable=False, ondelete="CASCADE")
    status: Mapped[str] = mapped_column(String(12), default="ringing", index=True)  # ringing|active|ended|missed|declined|cancelled
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    answered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    ended_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    end_reason: Mapped[str | None] = mapped_column(String(40))


class CallParticipant(Base):
    __tablename__ = "call_participants"
    call_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("calls.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), primary_key=True, index=True)
    state: Mapped[str] = mapped_column(String(10), default="ringing")  # ringing|joined|left|declined|missed
    joined_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    left_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    seen: Mapped[bool] = mapped_column(Boolean, default=True)  # False for unseen missed calls
