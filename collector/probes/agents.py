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
                    " count(*) FILTER (WHERE agent_last_seen_at > now() - interval '2 minutes'),"
                    " count(*) FILTER ("
                    "   WHERE agent_last_seen_at <= now() - interval '2 minutes'"
                    "     AND agent_status = 'active'"
                    " ),"
                    " count(*) FILTER (WHERE agent_status = 'active'),"
                    " count(*) "
                    "FROM agents"
                )
                healthy, stale, active_total, total = await cur.fetchone()
                # "green" overall if every active agent checked in recently
                up_status = "green" if stale == 0 else ("amber" if stale < active_total else "red")
                out.append(Sample("agents", "up", 1.0 if stale == 0 else 0.0, up_status))
                out.append(Sample("agents", "healthy", float(healthy), "green"))
                out.append(
                    Sample(
                        "agents",
                        "stale",
                        float(stale),
                        "red" if stale > 0 else "green",
                    )
                )
                out.append(Sample("agents", "active", float(active_total)))
                out.append(Sample("agents", "total", float(total)))
    except Exception as e:
        out.append(Sample("agents", "up", 0.0, "red", message=str(e)[:200]))
    return out
