from __future__ import annotations

from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from .. import models as m
from ..config import settings
from ..db import get_db
from ..deps import COOKIE, Ctx, audit, client_ip, current_ctx, rate_limited
from ..permissions import MATRIX, ROLE_LABELS, can
from ..security import (create_token, decrypt_secret, encrypt_secret, hash_password, mfa_uri,
                        new_mfa_secret, validate_password_strength, verify_mfa, verify_password)
from ..util import row

router = APIRouter(prefix="/auth", tags=["auth"])

MAX_FAILS = 5
LOCK_MINUTES = 15


class LoginIn(BaseModel):
    email: str
    password: str
    mfa_code: str | None = None


def _set_cookie(resp: Response, token: str) -> None:
    resp.set_cookie(COOKIE, token, httponly=True, secure=settings.cookie_secure, samesite="strict",
                    max_age=settings.jwt_ttl_minutes * 60, path="/")


@router.post("/login")
def login(body: LoginIn, request: Request, response: Response, db: Session = Depends(get_db)):
    user = authenticate(db, body, client_ip(request))
    token = create_token(user.id, user.role, user.token_version)
    _set_cookie(response, token)
    return {"ok": True, "token": token, "role": user.role}


def authenticate(db: Session, body: LoginIn, ip: str) -> m.User:
    """Shared by web and mobile sign-in: rate limit, lockout, password, MFA, audit."""
    if rate_limited(f"login:{ip}", settings.login_rate_limit_per_15m, 900):
        raise HTTPException(429, "Too many sign-in attempts. Try again in 15 minutes.")
    user = db.scalar(select(m.User).where(func.lower(m.User.email) == body.email.strip().lower()))
    now = datetime.now(timezone.utc)
    generic = HTTPException(401, "Email or password is incorrect.")
    if not user or not user.is_active:
        verify_password(body.password, "$2b$12$" + "x" * 53)  # equalise timing
        raise generic
    if user.locked_until and user.locked_until > now:
        raise HTTPException(423, "Account temporarily locked after repeated failures. Try again later.")
    if not verify_password(body.password, user.password_hash):
        user.failed_logins += 1
        if user.failed_logins >= MAX_FAILS:
            user.locked_until, user.failed_logins = now + timedelta(minutes=LOCK_MINUTES), 0
        audit(db, "auth.login_failed", "user", user.id, None, {}, user_id=user.id, label=user.email, ip=ip)
        db.commit()
        raise generic
    if user.mfa_enabled:
        if not body.mfa_code:
            raise HTTPException(401, detail={"mfa_required": True, "message": "Enter your authenticator code."})
        if not verify_mfa(decrypt_secret(user.mfa_secret_enc) or "", body.mfa_code):
            audit(db, "auth.mfa_failed", "user", user.id, None, {}, user_id=user.id, label=user.email, ip=ip)
            db.commit()
            raise HTTPException(401, detail={"mfa_required": True, "message": "Authenticator code is incorrect."})
    user.failed_logins, user.locked_until, user.last_login_at = 0, None, now
    audit(db, "auth.login", "user", user.id, None, {}, user_id=user.id, label=user.email, ip=ip)
    db.commit()
    return user


@router.post("/logout")
def logout(response: Response):
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.post("/logout-all")
def logout_all(response: Response, ctx: Ctx = Depends(current_ctx)):
    ctx.user.token_version += 1
    ctx.audit("auth.logout_all", "user", ctx.user.id)
    ctx.db.commit()
    response.delete_cookie(COOKIE, path="/")
    return {"ok": True}


@router.get("/me")
def me(ctx: Ctx = Depends(current_ctx)):
    person = ctx.db.get(m.Person, ctx.user.person_id) if ctx.user.person_id else None
    return {
        "user": row(ctx.user), "role_label": ROLE_LABELS.get(ctx.role, ctx.role),
        "person": row(person) if person else None,
        "permissions": sorted(a for a in MATRIX if can(ctx.role, a)),
        "scope": {"all_companies": ctx.scope.company_ids is None,
                  "company_ids": [str(c) for c in ctx.scope.company_ids or []],
                  "own_only": ctx.scope.own_only},
    }


class PwIn(BaseModel):
    current_password: str
    new_password: str


@router.post("/change-password")
def change_password(body: PwIn, ctx: Ctx = Depends(current_ctx)):
    if not verify_password(body.current_password, ctx.user.password_hash):
        raise HTTPException(400, "Current password is incorrect.")
    err = validate_password_strength(body.new_password)
    if err:
        raise HTTPException(400, err)
    ctx.user.password_hash = hash_password(body.new_password)
    ctx.user.token_version += 1
    ctx.audit("auth.password_changed", "user", ctx.user.id)
    ctx.db.commit()
    return {"ok": True, "message": "Password changed. Please sign in again."}


@router.post("/mfa/setup")
def mfa_setup(ctx: Ctx = Depends(current_ctx)):
    secret = new_mfa_secret()
    ctx.user.mfa_secret_enc = encrypt_secret(secret)
    ctx.db.commit()
    return {"secret": secret, "otpauth_uri": mfa_uri(secret, ctx.user.email)}


class CodeIn(BaseModel):
    code: str
    password: str | None = None


@router.post("/mfa/enable")
def mfa_enable(body: CodeIn, ctx: Ctx = Depends(current_ctx)):
    secret = decrypt_secret(ctx.user.mfa_secret_enc)
    if not secret or not verify_mfa(secret, body.code):
        raise HTTPException(400, "Code did not match. Check the time on your phone and try again.")
    ctx.user.mfa_enabled = True
    ctx.audit("auth.mfa_enabled", "user", ctx.user.id)
    ctx.db.commit()
    return {"ok": True}


@router.post("/mfa/disable")
def mfa_disable(body: CodeIn, ctx: Ctx = Depends(current_ctx)):
    if not body.password or not verify_password(body.password, ctx.user.password_hash):
        raise HTTPException(400, "Password is incorrect.")
    if not verify_mfa(decrypt_secret(ctx.user.mfa_secret_enc) or "", body.code):
        raise HTTPException(400, "Code is incorrect.")
    ctx.user.mfa_enabled, ctx.user.mfa_secret_enc = False, None
    ctx.audit("auth.mfa_disabled", "user", ctx.user.id)
    ctx.db.commit()
    return {"ok": True}
