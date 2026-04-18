"""Zitadel probe — /debug/ready + /debug/healthz latency."""
from __future__ import annotations

import time
import httpx

from . import Sample
from ..config import settings

name = "zitadel"


async def collect() -> list[Sample]:
    out: list[Sample] = []
    async with httpx.AsyncClient(timeout=5.0) as client:
        for path in ("/debug/healthz", "/debug/ready"):
            t0 = time.perf_counter()
            code = 0
            status = "red"
            try:
                r = await client.get(f"{settings.zitadel_url}{path}")
                code = r.status_code
                status = "green" if r.is_success else "amber"
            except Exception:
                status = "red"
            out.append(
                Sample(
                    "zitadel",
                    "latency_ms",
                    round((time.perf_counter() - t0) * 1000, 2),
                    status,
                    labels={"path": path, "code": str(code)},
                )
            )
    return out
