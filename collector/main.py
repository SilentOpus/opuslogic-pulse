"""Pulse collector entry point.

Runs the scheduler (probes → DuckDB) and serves:
  GET  /api/health          — liveness (unauthenticated)
  GET  /api/overview        — latest sample per (service, metric)
  GET  /api/range           — time-range query for timeline scrubber
  WS   /api/stream          — live sample broadcast (token via ?token=... query)

All /api/* endpoints except /api/health require a Zitadel bearer token with the
`platform.read` scope. WebSocket auth takes the token from the ?token query
param because browsers can't attach an Authorization header to the upgrade.
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import Depends, FastAPI, Query, WebSocket, WebSocketDisconnect, status
from fastapi.middleware.cors import CORSMiddleware

from .api.hub import Hub
from .auth import auth_required, require_user, verify_token_string
from .config import settings
from .scheduler import Scheduler
from .storage import Storage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s %(message)s"
)

storage = Storage(settings.db_path, retention_days=settings.retention_days)
hub = Hub()
scheduler = Scheduler(storage=storage, broadcast=hub.broadcast)

# In dev we can bypass OIDC via PULSE_AUTH_DISABLED=1.
_auth_dep = [Depends(require_user)] if auth_required() else []


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.start()
    try:
        yield
    finally:
        await scheduler.stop()


app = FastAPI(title="OpusLogic Pulse", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
async def health() -> dict:
    return {"ok": True, "probes": list(settings.enabled_probes)}


@app.get("/api/overview", dependencies=_auth_dep)
async def overview() -> dict:
    return {"samples": storage.latest_by_service()}


@app.get("/api/range", dependencies=_auth_dep)
async def range_(
    service: Optional[str] = None,
    minutes: int = Query(default=60, ge=1, le=60 * 24 * 7),
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return {"samples": storage.range(service, since)}


@app.websocket("/api/stream")
async def stream(ws: WebSocket, token: Optional[str] = Query(default=None)) -> None:
    if auth_required():
        if not token:
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            return
        try:
            await verify_token_string(token)
        except Exception:
            await ws.close(code=status.WS_1008_POLICY_VIOLATION)
            return

    await hub.connect(ws)
    try:
        await ws.send_json({"type": "snapshot", "samples": storage.latest_by_service()})
        while True:
            await ws.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(ws)
