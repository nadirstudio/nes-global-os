"""Request dependencies: authentication, authorization, scoping, auditing, rate limiting."""
from __future__ import annotations

import time
import uuid
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any

import redis
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from . import models as m
from .config import settings
from .db import get_db
from .permissions import Scope, can, scope_for
from .security import decode_token

COOKIE = "nes_session"

# ---------------------------------------------------------------- redis (optional)
_redis: redis.Redis | None = None


def get_redis() -> redis.Redis | None:
    global _redis
    if _redis is None:
        try:
            r = redis.Redis.from_url(settings.redis_url, socket_timeout=0.5, socket_connect_timeout=0.5)
            r.ping()
            _redis = r
        except Exception:
            return None
    return _redis


_mem_counters: dict[str, list[float]] = defaultdict(list)


def rate_limited(key: str, limit: int, window_s: int) -> bool:
    """True if the caller exceeded `limit` hits in `window_s`. Redis-backed, memory fallback."""
    r = get_redis()
    if r is not None:
        try:
            bucket = f"rl:{key}:{int(time.time() // window_s)}"
            n = r.incr(bucket)
            if n == 1:
                r.expire(bucket, window_s)
            return n > limit
        except Exception:
            pass
    now = time.time()
    hits = [t for t in _mem_counters[key] if now - t < window_s]
    hits.append(now)
    _mem_counters[key] = hits
    return len(hits) > limit


def client_ip(request: Request) -> str:
    fwd = request.headers.get("x-forwarded-for")
    return fwd.split(",")[0].strip() if fwd else (request.client.host if request.client else "?")


# ---------------------------------------------------------------- auth context
@dataclass
class Ctx:
    user: m.User
    scope: Scope
    db: Session
    ip: str
    device: "m.Device | None" = None

    @property
    def role(self) -> str:
        return self.user.role

    def audit(self, action: str, entity: str | None = None, entity_id: Any = None,
              company_id: uuid.UUID | None = None, **detail: Any) -> None:
        audit(self.db, action, entity, entity_id, company_id, detail,
              user_id=self.user.id, label=self.user.email, ip=self.ip)


def audit(db: Session, action: str, entity: str | None, entity_id: Any, company_id: uuid.UUID | None,
          detail: dict, user_id: uuid.UUID | None = None, agent_id: uuid.UUID | None = None,
          label: str | None = None, ip: str | None = None) -> None:
    clean = {k: (str(v) if isinstance(v, uuid.UUID) else v) for k, v in detail.items()}
    db.add(m.AuditLog(actor_user_id=user_id, actor_agent_id=agent_id, actor_label=label, action=action,
                      entity=entity, entity_id=str(entity_id) if entity_id else None,
                      company_id=company_id, detail=clean, ip=ip))


def _token_from(request: Request) -> str | None:
    auth = request.headers.get("authorization", "")
    if auth.lower().startswith("bearer "):
        return auth[7:].strip()
    return request.cookies.get(COOKIE)


def current_ctx(request: Request, db: Session = Depends(get_db)) -> Ctx:
    ip = client_ip(request)
    if rate_limited(f"api:{ip}", settings.api_rate_limit_per_min, 60):
        raise HTTPException(429, "Too many requests. Slow down.")
    token = _token_from(request)
    payload = decode_token(token) if token else None
    if not payload or not payload.get("mfa"):
        raise HTTPException(401, "Authentication required")
    if payload.get("typ") == "file":
        raise HTTPException(401, "Authentication required")
    user = db.get(m.User, uuid.UUID(payload["sub"]))
    if not user or not user.is_active or user.token_version != payload.get("tv"):
        raise HTTPException(401, "Session expired. Please sign in again.")
    device = None
    if payload.get("did"):
        device = db.get(m.Device, uuid.UUID(payload["did"]))
        if not device or device.user_id != user.id or device.revoked_at:
            raise HTTPException(401, detail={"device_revoked": True, "wipe": bool(device and device.wipe),
                                             "message": "This phone has been signed out by the administrator."})
        now = datetime.now(timezone.utc)
        if not device.last_seen_at or now - device.last_seen_at > timedelta(minutes=2):
            device.last_seen_at, device.last_ip = now, ip
            db.commit()
    return Ctx(user=user, scope=scope_for(db, user), db=db, ip=ip, device=device)


def require(action: str):
    def dep(ctx: Ctx = Depends(current_ctx)) -> Ctx:
        if not can(ctx.role, action):
            raise HTTPException(403, f"Your role is not permitted to perform: {action}")
        return ctx
    return dep


def ensure_company(ctx: Ctx, company_id: uuid.UUID | None) -> None:
    if not ctx.scope.allows_company(company_id):
        raise HTTPException(403, "This record belongs to a company outside your access.")


def ensure_department(ctx: Ctx, company_id: uuid.UUID | None, department_id: uuid.UUID | None) -> None:
    ensure_company(ctx, company_id)
    if ctx.scope.department_ids is not None and department_id not in ctx.scope.department_ids:
        raise HTTPException(403, "This record belongs to a department outside your access.")
