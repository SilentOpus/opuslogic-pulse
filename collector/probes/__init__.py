"""Probe registry. Each probe module exposes:

    name: str
    async def collect() -> list[Sample]

Samples are (service, metric, value, labels, status, message) tuples that the
scheduler writes to DuckDB and broadcasts to WebSocket listeners.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

Status = Literal["green", "amber", "red", "unknown"]


@dataclass
class Sample:
    service: str            # e.g. "backend", "postgres", "host"
    metric: str             # e.g. "cpu_pct", "latency_ms", "pool_in_use"
    value: float
    status: Status = "green"
    labels: dict[str, str] = field(default_factory=dict)
    message: str = ""
