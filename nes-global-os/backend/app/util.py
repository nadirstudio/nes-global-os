from __future__ import annotations

import uuid
from datetime import date, datetime
from decimal import Decimal
from typing import Any

from fastapi import HTTPException
from sqlalchemy import inspect
from sqlalchemy.orm import Session

HIDDEN = {"password_hash", "mfa_secret_enc", "api_key_enc"}


def jsonable(v: Any) -> Any:
    if isinstance(v, uuid.UUID):
        return str(v)
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    if isinstance(v, dict):
        return {k: jsonable(x) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [jsonable(x) for x in v]
    return v


def row(obj: Any, **extra: Any) -> dict:
    if obj is None:
        return None  # type: ignore[return-value]
    d = {c.key: jsonable(getattr(obj, c.key)) for c in inspect(obj).mapper.column_attrs if c.key not in HIDDEN}
    d.update({k: jsonable(v) for k, v in extra.items()})
    return d


def get_or_404(db: Session, model, ident, what: str = "Record"):
    try:
        key = uuid.UUID(str(ident)) if not isinstance(ident, uuid.UUID) else ident
    except ValueError:
        raise HTTPException(404, f"{what} not found")
    obj = db.get(model, key)
    if not obj:
        raise HTTPException(404, f"{what} not found")
    return obj


def apply(obj: Any, data: dict, allowed: set[str]) -> dict:
    changed = {}
    for k, v in data.items():
        if k in allowed and getattr(obj, k) != v:
            setattr(obj, k, v)
            changed[k] = v
    return changed
