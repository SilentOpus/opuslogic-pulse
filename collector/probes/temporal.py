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
        "PULSE_TEMPORAL_QUEUES",
        "default,agent_task_queue,activity-zone-default,default-activity,workflow-orchestration",
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
        # Activity-only queues won't show pollers under TASK_QUEUE_TYPE_WORKFLOW
        # and vice-versa. Infer the type from the queue name; query both if
        # ambiguous so we don't falsely show red.
        name_lc = q.lower()
        if "activity" in name_lc:
            types = [("activity", TaskQueueType.TASK_QUEUE_TYPE_ACTIVITY)]
        elif "workflow" in name_lc or "orchestration" in name_lc:
            types = [("workflow", TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW)]
        else:
            types = [
                ("workflow", TaskQueueType.TASK_QUEUE_TYPE_WORKFLOW),
                ("activity", TaskQueueType.TASK_QUEUE_TYPE_ACTIVITY),
            ]

        best_pollers = 0
        best_type = types[0][0]
        errs: list[str] = []
        for type_label, tq_type in types:
            try:
                req = DescribeTaskQueueRequest(
                    namespace="default",
                    task_queue=TaskQueue(name=q),
                    task_queue_type=tq_type,
                )
                resp: Any = await svc.describe_task_queue(req)
                pollers = len(resp.pollers) if hasattr(resp, "pollers") else 0
                if pollers > best_pollers:
                    best_pollers = pollers
                    best_type = type_label
            except Exception as e:
                errs.append(str(e)[:100])

        status = "green" if best_pollers > 0 else "red"
        labels = {"queue": q, "type": best_type}
        msg = "; ".join(errs) if (best_pollers == 0 and errs) else ""
        out.append(
            Sample(
                "temporal",
                "workers_reachable",
                float(best_pollers),
                status,
                labels=labels,
                message=msg,
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
