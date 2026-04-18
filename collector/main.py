"""Pulse collector entry point.

Runs the scheduler (probes → DuckDB) and serves:
  GET  /api/health          — liveness
  GET  /api/overview        — latest sample per (service, metric) for the Overview tab
  GET  /api/range           — time-range query for timeline scrubber
  WS   /api/stream          — live sample broadcast
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import FastAPI, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .api.hub import Hub
from .config import settings
from .scheduler import Scheduler
from .storage import Storage

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s %(levelname)-5s %(name)s %(message)s"
)

storage = Storage(settings.db_path, retention_days=settings.retention_days)
hub = Hub()
scheduler = Scheduler(storage=storage, broadcast=hub.broadcast)


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


@app.get("/api/overview")
async def overview() -> dict:
    return {"samples": storage.latest_by_service()}


@app.get("/api/range")
async def range_(
    service: Optional[str] = None,
    minutes: int = Query(default=60, ge=1, le=60 * 24 * 7),
) -> dict:
    since = datetime.now(timezone.utc) - timedelta(minutes=minutes)
    return {"samples": storage.range(service, since)}


@app.websocket("/api/stream")
async def stream(ws: WebSocket) -> None:
    await hub.connect(ws)
    try:
        # Send the current snapshot immediately so the UI can paint without waiting.
        await ws.send_json({"type": "snapshot", "samples": storage.latest_by_service()})
        while True:
            await ws.receive_text()  # we don't expect client messages; this keeps the socket alive
    except WebSocketDisconnect:
        pass
    finally:
        await hub.disconnect(ws)
