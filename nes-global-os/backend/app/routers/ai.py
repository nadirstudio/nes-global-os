"""AI provider credentials (admin only), model prices, budgets and the usage dashboard."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import func, select

from .. import models as m
from ..ai.providers import PROVIDERS, ProviderError, complete
from ..ai.runtime import (BUDGET_DEFAULTS, STATUS_FOR_ERROR, get_setting, period_starts, provider_cfg,
                          provider_key, provider_status, put_setting, spend)
from ..deps import Ctx, require
from ..security import encrypt_secret, key_hint
from ..util import row

router = APIRouter(prefix="/ai", tags=["ai"])


@router.get("/providers")
def providers(ctx: Ctx = Depends(require("ai.usage.view"))):
    out = []
    for p, meta in PROVIDERS.items():
        cfg = ctx.db.get(m.AIProviderConfig, p)
        _, src = provider_key(ctx.db, p)
        out.append({"provider": p, "label": meta["label"], "status": provider_status(ctx.db, p),
                    "key_source": src, "key_hint": cfg.key_hint if cfg else None,
                    "enabled": cfg.enabled if cfg else False, "base_url": cfg.base_url if cfg else None,
                    "last_error": cfg.last_error if cfg else None,
                    "last_checked_at": cfg.last_checked_at.isoformat() if cfg and cfg.last_checked_at else None})
    return out


class KeyIn(BaseModel):
    api_key: str | None = Field(default=None, min_length=8)
    base_url: str | None = None
    enabled: bool = True


@router.put("/providers/{provider}")
def set_provider(provider: str, body: KeyIn, ctx: Ctx = Depends(require("ai.settings"))):
    if provider not in PROVIDERS:
        raise HTTPException(404, "Unknown provider")
    if provider == "openai_compatible" and not (body.base_url or (ctx.db.get(m.AIProviderConfig, provider) or m.AIProviderConfig()).base_url):
        raise HTTPException(400, "An OpenAI-compatible provider needs a base URL")
    if body.base_url and not body.base_url.startswith("https://") and "localhost" not in body.base_url \
            and not body.base_url.startswith("http://10.") and not body.base_url.startswith("http://192.168."):
        raise HTTPException(400, "Base URL must use https (http only allowed on the local network)")
    cfg = provider_cfg(ctx.db, provider)
    if body.api_key:
        cfg.api_key_enc, cfg.key_hint = encrypt_secret(body.api_key.strip()), key_hint(body.api_key.strip())
        cfg.status, cfg.last_error = "CONFIGURED (UNTESTED)", None
    if body.base_url is not None:
        cfg.base_url = body.base_url or None
    cfg.enabled = body.enabled
    ctx.audit("ai.provider.update", "provider", provider, None, key_changed=bool(body.api_key), enabled=body.enabled)
    ctx.db.commit()
    return {"provider": provider, "status": provider_status(ctx.db, provider), "key_hint": cfg.key_hint}


@router.delete("/providers/{provider}")
def remove_key(provider: str, ctx: Ctx = Depends(require("ai.settings"))):
    cfg = provider_cfg(ctx.db, provider)
    cfg.api_key_enc, cfg.key_hint, cfg.enabled, cfg.status = None, None, False, "NOT CONNECTED"
    ctx.audit("ai.provider.remove_key", "provider", provider, None)
    ctx.db.commit()
    return {"provider": provider, "status": provider_status(ctx.db, provider)}


class TestModelIn(BaseModel):
    model: str


@router.post("/providers/{provider}/test")
def test_provider(provider: str, body: TestModelIn, ctx: Ctx = Depends(require("ai.settings"))):
    key, _ = provider_key(ctx.db, provider)
    cfg = provider_cfg(ctx.db, provider)
    if not key:
        raise HTTPException(400, "No API key configured for this provider")
    try:
        res = complete(provider, key, cfg.base_url, body.model, "Reply with the single word: OK", "Connectivity check", 10)
        cfg.status, cfg.last_error = "CONNECTED", None
        result = {"ok": True, "reply": res.text[:50], "tokens": res.input_tokens + res.output_tokens}
    except ProviderError as e:
        cfg.status, cfg.last_error = STATUS_FOR_ERROR.get(e.kind, "ERROR"), str(e)
        result = {"ok": False, "error": str(e)}
    cfg.last_checked_at = datetime.now(timezone.utc)
    ctx.audit("ai.provider.test", "provider", provider, None, ok=result["ok"], model=body.model)
    ctx.db.commit()
    return {**result, "status": cfg.status}


# ---------------------------------------------------------------- prices & budgets
class PriceIn(BaseModel):
    provider: str
    input_per_mtok: Decimal = Field(ge=0)
    output_per_mtok: Decimal = Field(ge=0)


@router.get("/prices")
def prices(ctx: Ctx = Depends(require("ai.usage.view"))):
    return [row(p) for p in ctx.db.scalars(select(m.ModelPrice).order_by(m.ModelPrice.model))]


@router.put("/prices/{model}")
def set_price(model: str, body: PriceIn, ctx: Ctx = Depends(require("ai.settings"))):
    p = ctx.db.get(m.ModelPrice, model) or m.ModelPrice(model=model)
    p.provider, p.input_per_mtok, p.output_per_mtok = body.provider, body.input_per_mtok, body.output_per_mtok
    ctx.db.merge(p)
    ctx.audit("ai.price.set", "model", model, None, input=str(body.input_per_mtok), output=str(body.output_per_mtok))
    ctx.db.commit()
    return row(ctx.db.get(m.ModelPrice, model))


class BudgetIn(BaseModel):
    monthly_limit_usd: Decimal | None = Field(default=None, ge=0)
    daily_limit_usd: Decimal | None = Field(default=None, ge=0)
    alert_pct: int = Field(default=80, ge=1, le=100)


@router.get("/budget")
def get_budget(ctx: Ctx = Depends(require("ai.usage.view"))):
    return get_setting(ctx.db, "ai_budget", BUDGET_DEFAULTS)


@router.put("/budget")
def put_budget(body: BudgetIn, ctx: Ctx = Depends(require("ai.settings"))):
    val = {k: (float(v) if isinstance(v, Decimal) else v) for k, v in body.model_dump().items()}
    put_setting(ctx.db, "ai_budget", val)
    ctx.audit("ai.budget.set", "setting", "ai_budget", None, **val)
    ctx.db.commit()
    return val


@router.get("/usage")
def usage(days: int = 30, ctx: Ctx = Depends(require("ai.usage.view"))):
    db = ctx.db
    since = datetime.now(timezone.utc) - timedelta(days=days)
    day_start, month_start = period_starts()
    budget = get_setting(db, "ai_budget", BUDGET_DEFAULTS)
    month_spend, day_spend = float(spend(db, month_start)), float(spend(db, day_start))
    by_agent = db.execute(select(m.Agent.id, m.Agent.name, m.Agent.monthly_budget, func.count(m.AgentRun.id),
                                 func.sum(m.AgentRun.input_tokens), func.sum(m.AgentRun.output_tokens),
                                 func.sum(m.AgentRun.cost), func.count().filter(m.AgentRun.status != "succeeded"))
                          .join(m.AgentRun, m.AgentRun.agent_id == m.Agent.id)
                          .where(m.AgentRun.started_at >= since).group_by(m.Agent.id)
                          .order_by(func.sum(m.AgentRun.cost).desc())).all()
    by_model = db.execute(select(m.AgentRun.provider, m.AgentRun.model, func.count(), func.sum(m.AgentRun.input_tokens),
                                 func.sum(m.AgentRun.output_tokens), func.sum(m.AgentRun.cost),
                                 func.bool_and(m.AgentRun.priced))
                          .where(m.AgentRun.started_at >= since, m.AgentRun.model.is_not(None))
                          .group_by(m.AgentRun.provider, m.AgentRun.model)).all()
    day_col = func.date_trunc("day", m.AgentRun.started_at)
    daily = db.execute(select(day_col, func.sum(m.AgentRun.cost),
                              func.sum(m.AgentRun.input_tokens + m.AgentRun.output_tokens), func.count())
                       .where(m.AgentRun.started_at >= since).group_by(day_col).order_by(day_col)).all()
    alerts = []
    for label, used, lim in [("monthly", month_spend, budget.get("monthly_limit_usd")),
                             ("daily", day_spend, budget.get("daily_limit_usd"))]:
        if lim:
            pct = 100 * used / float(lim)
            if pct >= 100:
                alerts.append({"severity": "critical", "title": f"{label.title()} AI budget reached"})
            elif pct >= budget.get("alert_pct", 80):
                alerts.append({"severity": "warning", "title": f"{label.title()} AI budget at {pct:.0f}%"})
    return {
        "budget": budget, "month_spend_usd": month_spend, "today_spend_usd": day_spend, "alerts": alerts,
        "by_agent": [{"agent_id": str(a), "name": n, "monthly_budget": float(b) if b else None, "runs": r,
                      "input_tokens": int(i or 0), "output_tokens": int(o or 0), "cost_usd": float(c or 0),
                      "non_success": ns} for a, n, b, r, i, o, c, ns in by_agent],
        "by_model": [{"provider": p, "model": mo, "runs": r, "input_tokens": int(i or 0), "output_tokens": int(o or 0),
                      "cost_usd": float(c or 0), "fully_priced": bool(pr)} for p, mo, r, i, o, c, pr in by_model],
        "daily": [{"day": d.date().isoformat(), "cost_usd": float(c or 0), "tokens": int(t or 0), "runs": n}
                  for d, c, t, n in daily],
    }
