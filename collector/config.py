"""Pulse collector configuration. All values come from env vars with sane defaults."""
from __future__ import annotations

import os
from dataclasses import dataclass


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
    postgres_dsn: str = os.getenv(
        "PULSE_POSTGRES_DSN", "postgresql://flows_user:changeme@postgres:5432/flows"
    )

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
