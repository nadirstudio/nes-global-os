"""NES GLOBAL OS — API entrypoint."""
from __future__ import annotations

import logging
import os
import time
import uuid

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .config import settings
from .realtime import hub as rt_hub
from .routers import agents, ai, assistant, auth, business, calls, hub, mobile, org, people, system, work

log = logging.getLogger("nes.api")
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")

@asynccontextmanager
async def lifespan(_app: FastAPI):
    await rt_hub.start()
    try:
        calls.cleanup_stale_calls()
    except Exception:
        log.warning("call cleanup skipped (database not ready?)")
    yield
    await rt_hub.stop()


app = FastAPI(title="NES GLOBAL OS API", version="1.2.0", lifespan=lifespan,
              docs_url="/api/docs" if settings.env != "production" else None, openapi_url="/api/openapi.json")

if settings.cors_origins:
    # The Android app (origin https://localhost) authenticates with a Bearer token, never cookies.
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_credentials=False,
                       allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE"],
                       allow_headers=["authorization", "content-type"], max_age=600)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    rid = request.headers.get("x-request-id") or uuid.uuid4().hex[:12]
    start = time.perf_counter()
    try:
        resp = await call_next(request)
    except Exception:
        log.exception("unhandled error rid=%s %s %s", rid, request.method, request.url.path)
        resp = JSONResponse({"detail": "Internal error. Reference: " + rid}, status_code=500)
    resp.headers["x-request-id"] = rid
    resp.headers["x-content-type-options"] = "nosniff"
    resp.headers["x-frame-options"] = "DENY"
    resp.headers["referrer-policy"] = "same-origin"
    resp.headers["cache-control"] = "no-store"
    ms = (time.perf_counter() - start) * 1000
    if resp.status_code >= 400 or ms > 1500:
        log.info("%s %s -> %s %.0fms rid=%s", request.method, request.url.path, resp.status_code, ms, rid)
    return resp


for r in (auth.router, org.router, people.router, agents.router, work.router, business.router,
          ai.router, system.router, assistant.router, mobile.router, hub.router, calls.router):
    app.include_router(r, prefix="/api")


# Optional: serve the built frontend from the API process (single-process installs / testing).
# In the standard deployment Caddy serves the frontend and proxies /api.
_static = os.getenv("NES_STATIC_DIR")
if _static and os.path.isdir(_static):
    from fastapi.staticfiles import StaticFiles
    app.mount("/", StaticFiles(directory=_static, html=True), name="web")
