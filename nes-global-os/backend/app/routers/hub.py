"""Employee Hub administration (web portal): work sites, devices, HR policies, documents, file serving."""
from __future__ import annotations

import hashlib
import io
import os
import re
import uuid
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from .. import models as m
from ..ai.runtime import get_setting, put_setting
from ..config import settings
from ..db import get_db
from ..deps import Ctx, current_ctx, ensure_company, require
from ..security import decode_token
from ..util import apply, get_or_404, row
from .mobile import (ATTENDANCE_POLICY_DEFAULT, LEAVE_KINDS, LEAVE_POLICY_DEFAULT, _leave_view, can_manage_person,
                     doc_visible)

router = APIRouter(tags=["employee-hub"])


def _now() -> datetime:
    return datetime.now(timezone.utc)


# ================================================================ work sites (geofences)
class SiteIn(BaseModel):
    name: str = Field(min_length=2, max_length=200)
    company_id: uuid.UUID | None = None
    kind: str = "office"
    lat: float = Field(ge=-90, le=90)
    lng: float = Field(ge=-180, le=180)
    radius_m: int = Field(default=150, ge=30, le=5000)
    active: bool = True


@router.get("/hub/sites")
def sites(ctx: Ctx = Depends(require("attendance.manage"))):
    return [row(s) for s in ctx.db.scalars(select(m.WorkSite).order_by(m.WorkSite.name))
            if s.company_id is None or ctx.scope.allows_company(s.company_id)]


@router.post("/hub/sites", status_code=201)
def add_site(body: SiteIn, ctx: Ctx = Depends(require("department.manage"))):
    if body.company_id:
        ensure_company(ctx, body.company_id)
    elif ctx.role != "ceo":
        raise HTTPException(403, "Only the CEO can add group-wide sites")
    if body.kind not in {"office", "branch", "client"}:
        raise HTTPException(400, "Kind must be office, branch or client")
    s = m.WorkSite(**body.model_dump())
    ctx.db.add(s)
    ctx.db.flush()
    ctx.audit("site.create", "work_site", s.id, s.company_id, name=s.name, radius=s.radius_m)
    ctx.db.commit()
    return row(s)


@router.patch("/hub/sites/{sid}")
def edit_site(sid: str, body: SiteIn, ctx: Ctx = Depends(require("department.manage"))):
    s = get_or_404(ctx.db, m.WorkSite, sid, "Site")
    if s.company_id:
        ensure_company(ctx, s.company_id)
    elif ctx.role != "ceo":
        raise HTTPException(403, "Only the CEO can edit group-wide sites")
    changed = apply(s, body.model_dump(), set(SiteIn.model_fields))
    ctx.audit("site.update", "work_site", s.id, s.company_id, fields=sorted(changed))
    ctx.db.commit()
    return row(s)


# ================================================================ devices (remote sign-out / wipe)
@router.get("/hub/devices")
def devices(ctx: Ctx = Depends(require("users.manage"))):
    out = []
    for d in ctx.db.scalars(select(m.Device).order_by(m.Device.last_seen_at.desc().nulls_last()).limit(500)):
        u = ctx.db.get(m.User, d.user_id)
        p = ctx.db.get(m.Person, u.person_id) if u and u.person_id else None
        out.append(row(d, user=p.full_name if p else (u.email if u else None), email=u.email if u else None))
    return out


class RevokeIn(BaseModel):
    wipe: bool = True


@router.post("/hub/devices/{did}/revoke")
def revoke(did: str, body: RevokeIn, ctx: Ctx = Depends(require("users.manage"))):
    d = get_or_404(ctx.db, m.Device, did, "Device")
    d.revoked_at, d.wipe = d.revoked_at or _now(), body.wipe
    ctx.audit("device.revoke", "device", d.id, None, wipe=body.wipe)
    ctx.db.commit()
    return row(d)


# ================================================================ HR policies
class LeavePolicyIn(BaseModel):
    annual: float = Field(ge=0, le=365)
    casual: float = Field(ge=0, le=365)
    sick: float = Field(ge=0, le=365)


@router.get("/hub/policies")
def policies(ctx: Ctx = Depends(require("attendance.manage"))):
    return {"leave": get_setting(ctx.db, "leave_policy", LEAVE_POLICY_DEFAULT),
            "attendance": get_setting(ctx.db, "attendance_policy", ATTENDANCE_POLICY_DEFAULT), "leave_kinds": LEAVE_KINDS}


@router.put("/hub/policies/leave")
def put_leave_policy(body: LeavePolicyIn, ctx: Ctx = Depends(require("company.manage"))):
    put_setting(ctx.db, "leave_policy", body.model_dump())
    ctx.audit("policy.leave", "setting", "leave_policy", None, **body.model_dump())
    ctx.db.commit()
    return body.model_dump()


class AttPolicyIn(BaseModel):
    require_biometric: bool = True
    late_grace_minutes: int = Field(default=15, ge=0, le=180)
    max_gps_accuracy_m: int = Field(default=200, ge=20, le=2000)
    allow_web_checkin_with_sites: bool = False


@router.put("/hub/policies/attendance")
def put_att_policy(body: AttPolicyIn, ctx: Ctx = Depends(require("company.manage"))):
    put_setting(ctx.db, "attendance_policy", body.model_dump())
    ctx.audit("policy.attendance", "setting", "attendance_policy", None, **body.model_dump())
    ctx.db.commit()
    return body.model_dump()


@router.get("/hub/leave")
def all_leave(status: str = "pending", ctx: Ctx = Depends(require("attendance.manage"))):
    q = select(m.LeaveRequest).order_by(m.LeaveRequest.start_on.desc()).limit(500)
    if status != "all":
        q = q.where(m.LeaveRequest.status == status)
    out = []
    for lr in ctx.db.scalars(q):
        p = ctx.db.get(m.Person, lr.person_id)
        if p and (ctx.role == "ceo" or can_manage_person(ctx, p)):
            v = _leave_view(ctx.db, lr, with_person=True)
            v["can_decide"] = lr.status == "pending" and (ctx.role == "ceo" or can_manage_person(ctx, p))
            out.append(v)
    return out


# ================================================================ documents
ALLOWED = {
    "application/pdf": (".pdf", lambda b: b.startswith(b"%PDF")),
    "image/png": (".png", lambda b: b.startswith(b"\x89PNG")),
    "image/jpeg": (".jpg", lambda b: b.startswith(b"\xff\xd8\xff")),
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": (".docx", lambda b: b.startswith(b"PK")),
    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet": (".xlsx", lambda b: b.startswith(b"PK")),
    "text/plain": (".txt", None),
    "text/markdown": (".md", None),
}
EXT_MIME = {v[0]: k for k, v in ALLOWED.items()} | {".jpeg": "image/jpeg", ".markdown": "text/markdown"}
CATEGORIES = ["policy", "sop", "handbook", "training", "contract", "form"]


def detect(name: str, data: bytes) -> str:
    ext = os.path.splitext(name.lower())[1]
    mime = EXT_MIME.get(ext)
    if not mime:
        raise HTTPException(400, "Allowed files: PDF, Word (.docx), Excel (.xlsx), PNG, JPG, TXT, MD")
    check = ALLOWED[mime][1]
    if check and not check(data[:8]):
        raise HTTPException(400, "The file content doesn't match its extension")
    if check is None:
        try:
            data.decode("utf-8")
        except UnicodeDecodeError:
            raise HTTPException(400, "Text files must be UTF-8")
    return mime


def extract_text(mime: str, data: bytes) -> str | None:
    try:
        if mime in {"text/plain", "text/markdown"}:
            return data.decode("utf-8")
        if mime == "application/pdf":
            from pypdf import PdfReader
            r = PdfReader(io.BytesIO(data))
            return "\n".join((pg.extract_text() or "") for pg in r.pages[:200]).strip() or None
        if mime.endswith("wordprocessingml.document"):
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                xml = z.read("word/document.xml").decode("utf-8", "ignore")
            xml = re.sub(r"</w:p>", "\n", xml)
            return re.sub(r"<[^>]+>", "", xml).strip() or None
    except Exception:
        return None
    return None


def _can_publish(ctx: Ctx, company_id, department_id, person_id) -> None:
    if ctx.role not in {"ceo", "director", "dept_head"}:
        raise HTTPException(403, "Only the CEO, directors and department heads can publish documents")
    if person_id:
        p = get_or_404(ctx.db, m.Person, person_id, "Person")
        if not (ctx.role == "ceo" or can_manage_person(ctx, p)):
            raise HTTPException(403, "That person is outside your team")
        return
    if department_id:
        d = get_or_404(ctx.db, m.Department, department_id, "Department")
        ensure_company(ctx, d.company_id)
        if ctx.scope.department_ids is not None and d.id not in ctx.scope.department_ids:
            raise HTTPException(403, "That department is outside your access")
    elif company_id:
        if ctx.role == "dept_head":
            raise HTTPException(403, "Department heads publish to their department")
        ensure_company(ctx, company_id)
    elif ctx.role != "ceo":
        raise HTTPException(403, "Only the CEO can publish to the whole group")


def _opt_uuid(v: str | None) -> uuid.UUID | None:
    return uuid.UUID(v) if v else None


@router.post("/hub/documents", status_code=201)
async def upload_document(title: str = Form(...), category: str = Form(...), company_id: str | None = Form(None),
                          department_id: str | None = Form(None), person_id: str | None = Form(None),
                          leaders_only: bool = Form(False), body_text: str | None = Form(None),
                          file: UploadFile | None = File(None), ctx: Ctx = Depends(current_ctx)):
    if category not in CATEGORIES:
        raise HTTPException(400, f"Category must be one of {CATEGORIES}")
    cid, did, pid = _opt_uuid(company_id), _opt_uuid(department_id), _opt_uuid(person_id)
    _can_publish(ctx, cid, did, pid)
    if did and not cid:
        cid = ctx.db.get(m.Department, did).company_id
    if not file and not (body_text and body_text.strip()):
        raise HTTPException(400, "Attach a file or write the text")
    doc = m.Document(title=title.strip()[:300], category=category, company_id=cid, department_id=did, person_id=pid,
                     leaders_only=leaders_only, body_text=(body_text or "").strip() or None, uploaded_by_user_id=ctx.user.id)
    if file:
        data = await file.read(settings.max_upload_mb * 1024 * 1024 + 1)
        if len(data) > settings.max_upload_mb * 1024 * 1024:
            raise HTTPException(413, f"File is larger than {settings.max_upload_mb} MB")
        if not data:
            raise HTTPException(400, "The file is empty")
        mime = detect(file.filename or "", data)
        os.makedirs(settings.files_dir, exist_ok=True)
        doc.id = uuid.uuid4()
        path = os.path.join(settings.files_dir, f"{doc.id}{ALLOWED[mime][0]}")
        with open(path, "wb") as fh:
            fh.write(data)
        doc.file_name = os.path.basename(file.filename or "file")[:300]
        doc.file_path, doc.mime, doc.size_bytes = path, mime, len(data)
        doc.sha256 = hashlib.sha256(data).hexdigest()
        if not doc.body_text:
            doc.body_text = extract_text(mime, data)
    ctx.db.add(doc)
    ctx.db.flush()
    ctx.audit("document.publish", "document", doc.id, doc.company_id, title=doc.title, category=category)
    ctx.db.commit()
    return row(doc)


@router.get("/hub/documents")
def list_documents(ctx: Ctx = Depends(current_ctx)):
    return [row(d) for d in ctx.db.scalars(select(m.Document).order_by(m.Document.updated_at.desc())) if doc_visible(ctx, d)]


@router.delete("/hub/documents/{did}")
def delete_document(did: str, ctx: Ctx = Depends(current_ctx)):
    d = get_or_404(ctx.db, m.Document, did, "Document")
    if not (ctx.role == "ceo" or d.uploaded_by_user_id == ctx.user.id):
        raise HTTPException(403, "Only the uploader or the CEO can remove a document")
    if d.file_path and os.path.isfile(d.file_path):
        os.remove(d.file_path)
    ctx.audit("document.delete", "document", d.id, d.company_id, title=d.title)
    ctx.db.delete(d)
    ctx.db.commit()
    return {"ok": True}


@router.get("/files/{did}")
def serve_file(did: str, t: str, db: Session = Depends(get_db)):
    """Opened by the phone's viewer via a 5-minute, single-document link from /mobile/documents/{id}/link."""
    payload = decode_token(t)
    if not payload or payload.get("typ") != "file" or payload.get("doc") != did:
        raise HTTPException(403, "This link has expired. Open the document again from the app.")
    d = get_or_404(db, m.Document, did, "Document")
    user = db.get(m.User, uuid.UUID(payload["sub"]))
    if not user or not user.is_active:
        raise HTTPException(403, "Not allowed")
    from ..permissions import scope_for
    ctx = Ctx(user=user, scope=scope_for(db, user), db=db, ip="")
    if not doc_visible(ctx, d) or not d.file_path or not os.path.isfile(d.file_path):
        raise HTTPException(404, "File not available")
    return FileResponse(d.file_path, media_type=d.mime, filename=d.file_name,
                        content_disposition_type="inline", headers={"Cache-Control": "no-store"})
