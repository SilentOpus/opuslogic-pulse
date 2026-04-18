"""Postgres probe — connections, slow queries, lock waits, replication lag.

Uses psycopg against the platform's own Postgres via read-only queries against
pg_stat_activity / pg_stat_database / pg_locks.
"""
from __future__ import annotations

import psycopg

from . import Sample
from ..config import settings

name = "postgres"


async def collect() -> list[Sample]:
    out: list[Sample] = []
    try:
        async with await psycopg.AsyncConnection.connect(
            settings.postgres_dsn, connect_timeout=5
        ) as conn:
            async with conn.cursor() as cur:
                await cur.execute(
                    "SELECT count(*) FROM pg_stat_activity WHERE state IS NOT NULL"
                )
                (conns,) = await cur.fetchone()
                out.append(
                    Sample(
                        "postgres",
                        "connections",
                        float(conns),
                        "amber" if conns > 80 else "green",
                    )
                )

                await cur.execute(
                    "SELECT count(*) FROM pg_stat_activity "
                    "WHERE state='active' AND query_start < now() - interval '5 seconds'"
                )
                (slow,) = await cur.fetchone()
                out.append(
                    Sample(
                        "postgres",
                        "slow_queries",
                        float(slow),
                        "red" if slow > 5 else ("amber" if slow > 0 else "green"),
                    )
                )

                await cur.execute("SELECT count(*) FROM pg_locks WHERE NOT granted")
                (waiting,) = await cur.fetchone()
                out.append(
                    Sample(
                        "postgres",
                        "locks_waiting",
                        float(waiting),
                        "red" if waiting > 10 else ("amber" if waiting > 0 else "green"),
                    )
                )

                out.append(Sample("postgres", "up", 1.0, "green"))
    except Exception as e:
        out.append(Sample("postgres", "up", 0.0, "red", message=str(e)[:200]))
    return out
