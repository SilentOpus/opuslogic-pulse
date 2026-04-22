"""Pulse collector configuration.

Operational config (host/port/intervals) has sane defaults; secrets
and tenant-specific connection strings do NOT — they must be supplied
explicitly via env. Mirrors the gtm-crm/backend/src/db.py pattern.
"""
from __future__ import annotations

import os
from dataclasses import dataclass


def _required_env(name: str) -> str:
    """Fetch an env var that has no safe default (typically secret-bearing).
    Raise immediately at startup if missing — no silent fallback to a
    sentinel password (the previous default was 'changeme', which would
    quietly try a known-bad credential in any unconfigured environment).
    """
    val = os.environ.get(name, "")
    if not val:
        raise RuntimeError(
            f"{name} env var must be set explicitly. There is no default — "
            "see opuslogic-pulse/README.md for required env vars."
        )
    return val


@dataclass(frozen=True)
class Settings:
    db_path: str = os.getenv("PULSE_DB_PATH", "/data/pulse.duckdb")
    poll_interval_seconds: int = int(os.getenv("PULSE_POLL_INTERVAL", "10"))
    retention_days: int = int(os.getenv("PULSE_RETENTION_DAYS", "90"))

    host: str = os.getenv("PULSE_HOST", "0.0.0.0")
    port: int = int(os.getenv("PULSE_PORT", "7500"))

    # Target service URLs — collector reaches the platform via these
    backend_url: str = os.getenv("PULSE_BACKEND_URL", "https://backend:7443")
    zitadel_url: str = os.getenv("PULSE_ZITADEL_URL", "http://zitadel:8080")
    temporal_url: str = os.getenv("PULSE_TEMPORAL_URL", "temporal-server:7233")

    # Required: no default. Previously had a 'changeme' fallback DSN
    # which would silently attempt a known-bad credential against the
    # platform Postgres in any unconfigured environment.
    postgres_dsn: str = _required_env("PULSE_POSTGRES_DSN")

    # Probes can be disabled via env for local dev
    enabled_probes: tuple[str, ...] = tuple(
        p.strip()
        for p in os.getenv(
            "PULSE_ENABLED_PROBES",
            "host,backend,temporal,postgres,zitadel,docker,agents",
        ).split(",")
        if p.strip()
    )


settings = Settings()
