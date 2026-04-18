"""Docker probe — queries the Docker socket for container state + per-container
CPU/memory. Uses the REST API directly (no SDK dep).

Container list filters to those with the opuslogic compose project label so the
dashboard only shows relevant containers.
"""
from __future__ import annotations

import json

import httpx

from . import Sample

name = "docker"

_DOCKER_SOCK = "http://docker/"
_TRANSPORT = httpx.AsyncHTTPTransport(uds="/var/run/docker.sock")
_PROJECT_FILTER = {"label": ["com.docker.compose.project=opuslogic"]}


async def collect() -> list[Sample]:
    out: list[Sample] = []
    try:
        async with httpx.AsyncClient(transport=_TRANSPORT, timeout=5.0) as client:
            r = await client.get(
                f"{_DOCKER_SOCK}containers/json",
                params={"all": "true", "filters": json.dumps(_PROJECT_FILTER)},
            )
            containers = r.json()

            for c in containers:
                name_ = (c.get("Names") or ["?"])[0].lstrip("/")
                state = c.get("State", "unknown")
                status = "green" if state == "running" else ("amber" if state == "restarting" else "red")
                out.append(
                    Sample("docker", "up", 1.0 if state == "running" else 0.0, status,
                           labels={"container": name_, "state": state})
                )
    except Exception as e:
        out.append(Sample("docker", "up", 0.0, "red", message=str(e)[:200]))
    return out
