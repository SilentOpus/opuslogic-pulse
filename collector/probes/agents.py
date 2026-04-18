"""Agents probe — reads agent heartbeats from the platform's Postgres."""
from __future__ import annotations

import psycopg

from . import Sample
from ..config import settings

name = "agents"


async def collect() -> list[Sample]:
    out: list[Sample] = []
    try:
        async with await psycopg.AsyncConnection.connect(
            settings.postgres_dsn, connect_timeout=5
        ) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT "
                    " count(*) FILTER (WHERE last_heartbeat_at > now() - interval '2 minutes'),"
                    " count(*) FILTER (WHERE last_heartbeat_at <= now() - interval '2 minutes'),"
                    " count(*) "
                    "FROM agents"
                )
                healthy, stale, total = await cur.fetchone()
                out.append(Sample("agents", "healthy", float(healthy), "green"))
                out.append(
                    Sample(
                        "agents",
                        "stale",
                        float(stale),
                        "red" if stale > 0 else "green",
                    )
                )
                out.append(Sample("agents", "total", float(total)))
    except Exception as e:
        out.append(Sample("agents", "up", 0.0, "red", message=str(e)[:200]))
    return out
