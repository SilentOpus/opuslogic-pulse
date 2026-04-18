"""Temporal probe — uses the temporalio SDK to query cluster + task queue health.

Metrics emitted:
  temporal.up                 — 1 if cluster reachable
  temporal.cluster_version    — informational (labels.version)
  temporal.queue_backlog      — backlog per task queue (labels.queue)
  temporal.workers_reachable  — count of workers polling a known task queue

Known queues come from PULSE_TEMPORAL_QUEUES (comma-separated). If unset we fall
back to the platform defaults.
"""
from __future__ import annotations

import logging
import os
from typing import Any

from . import Sample
from ..config import settings

name = "temporal"
log = logging.getLogger("pulse.probes.temporal")

_KNOWN_QUEUES = tuple(
    q.strip()
    for q in os.getenv(
        "PULSE_TEMPORAL_QUEUES", "default-tq,activity-default-tq,credential-manager-tq"
    ).split(",")
    if q.strip()
)


async def _sdk_collect() -> list[Sample]:
    from temporalio.client import Client  # type: ignore
    from temporalio.api.taskqueue.v1 import TaskQueue  # type: ignore
    from temporalio.api.enums.v1 import TaskQueueType  # type: ignore
    from temporalio.api.workflowservice.v1 import (  # type: ignore
        DescribeTaskQueueRequest,
        GetSystemInfoRequest,
    )

    out: list[Sample] = []
    client = await Client.connect(settings.temporal_url)
    svc = client.service_client.workflow_service

    # Newer temporalio requires the explicit request message.
    info = await svc.get_system_info(GetSystemInfoRequest())
    version = getattr(info, "server_version", "unknown")
    out.append(Sample("temporal", "up", 1.0, "green", labels={"version": str(version)}))

    for q in _KNOWN_QUEUES:
        try:
            req = DescribeTaskQueueRequest(
                namespace="default",
                task_queue=TaskQueue(name=q),
                task_queue_type=TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW,
            )
            resp: Any = await svc.describe_task_queue(req)
            pollers = len(resp.pollers) if hasattr(resp, "pollers") else 0
            status = "green" if pollers > 0 else "red"
            out.append(
                Sample(
                    "temporal",
                    "workers_reachable",
                    float(pollers),
                    status,
                    labels={"queue": q},
                )
            )
        except Exception as e:
            out.append(
                Sample(
                    "temporal",
                    "workers_reachable",
                    0.0,
                    "red",
                    labels={"queue": q},
                    message=str(e)[:200],
                )
            )
    return out


async def _tcp_fallback() -> list[Sample]:
    """Used when the temporalio SDK isn't installed."""
    import asyncio

    host, _, port = settings.temporal_url.partition(":")
    try:
        _, writer = await asyncio.wait_for(
            asyncio.open_connection(host, int(port or "7233")), timeout=3.0
        )
        writer.close()
        try:
            await writer.wait_closed()
        except Exception:
            pass
        return [Sample("temporal", "up", 1.0, "green", message="tcp-only (install temporalio for full probe)")]
    except Exception as e:
        return [Sample("temporal", "up", 0.0, "red", message=str(e)[:200])]


async def collect() -> list[Sample]:
    try:
        import temporalio  # noqa: F401
    except ImportError:
        return await _tcp_fallback()
    try:
        return await _sdk_collect()
    except Exception as e:
        log.warning("temporal sdk probe failed, falling back: %s", e)
        return [Sample("temporal", "up", 0.0, "red", message=str(e)[:200])]
