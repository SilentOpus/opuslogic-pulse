"""Backend probe.

On each tick:
  1. Fetches /openapi.json (cached with a short TTL) to discover every GET
     endpoint exposed by the backend.
  2. Picks a rotating sample of routes (so we don't hammer the API every cycle)
     and measures per-route latency + status code.
  3. Always hits /health and /ready so top-of-dashboard indicators stay fresh.

Each sample carries the route as a label, so the Backend API tab can render a
per-endpoint latency table.
"""
from __future__ import annotations

import itertools
import logging
import re
import time
from typing import Iterable

import httpx

from . import Sample
from ..config import settings

name = "backend"
log = logging.getLogger("pulse.probes.backend")

_ALWAYS = ("/backend/health", "/backend/ready")
_PATH_VAR_RE = re.compile(r"\{[^}]+\}")

_openapi_cache: dict[str, object] = {"ts": 0.0, "routes": []}
_OPENAPI_TTL = 300.0  # 5 min
_SAMPLES_PER_TICK = 5
_route_cycle: itertools.cycle | None = None
_route_cycle_source_id: int | None = None


async def _fetch_openapi(client: httpx.AsyncClient) -> list[str]:
    now = time.time()
    if now - float(_openapi_cache["ts"]) < _OPENAPI_TTL and _openapi_cache["routes"]:
        return _openapi_cache["routes"]  # type: ignore[return-value]

    try:
        r = await client.get(f"{settings.backend_url}/backend/openapi.json")
        r.raise_for_status()
        doc = r.json()
    except Exception as e:
        log.warning("openapi fetch failed: %s", e)
        return []

    routes: list[str] = []
    for path, ops in (doc.get("paths") or {}).items():
        if not isinstance(ops, dict) or "get" not in ops:
            continue
        # Skip templated paths — we have no way to synthesize valid values.
        if _PATH_VAR_RE.search(path):
            continue
        prefixed = path if path.startswith("/backend") else f"/backend{path}"
        if prefixed in _ALWAYS:
            continue
        routes.append(prefixed)

    routes.sort()
    _openapi_cache["ts"] = now
    _openapi_cache["routes"] = routes
    log.info("openapi: discovered %d probeable GET routes", len(routes))
    return routes


def _next_rotating(routes: list[str]) -> list[str]:
    global _route_cycle, _route_cycle_source_id
    if not routes:
        return []
    if _route_cycle is None or _route_cycle_source_id != id(routes):
        _route_cycle = itertools.cycle(routes)
        _route_cycle_source_id = id(routes)
    return [next(_route_cycle) for _ in range(min(_SAMPLES_PER_TICK, len(routes)))]


async def _probe(client: httpx.AsyncClient, route: str) -> Iterable[Sample]:
    t0 = time.perf_counter()
    code = 0
    try:
        r = await client.get(f"{settings.backend_url}{route}")
        code = r.status_code
        if r.is_success:
            status = "green"
        elif 400 <= r.status_code < 500:
            # 401/403 are expected for unauthenticated synthetic probes — still "alive".
            status = "green" if r.status_code in (401, 403) else "amber"
        else:
            status = "red"
    except Exception:
        status = "red"
    latency = round((time.perf_counter() - t0) * 1000, 2)
    yield Sample(
        "backend",
        "latency_ms",
        latency,
        status,
        labels={"route": route, "code": str(code)},
    )
    yield Sample(
        "backend",
        "up",
        1.0 if status != "red" else 0.0,
        status,
        labels={"route": route},
    )


async def collect() -> list[Sample]:
    out: list[Sample] = []
    async with httpx.AsyncClient(verify=False, timeout=5.0) as client:
        routes = await _fetch_openapi(client)
        to_probe = list(_ALWAYS) + _next_rotating(routes)
        for route in to_probe:
            async for s in _probe(client, route):
                out.append(s)
    return out
