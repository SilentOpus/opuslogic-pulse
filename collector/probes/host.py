"""Host probe — reads /proc to surface CPU, memory, load, disk, network.

No external deps; parses procfs directly so the container just needs /proc
and /sys mounted from the host (handled in docker-compose).
"""
from __future__ import annotations

import os
import time
from typing import Iterable

from . import Sample

name = "host"

_PROC = os.getenv("PULSE_PROC_PATH", "/host/proc")
_SYS = os.getenv("PULSE_SYS_PATH", "/host/sys")

_prev_cpu: tuple[int, int] | None = None  # (idle, total)
_prev_net: dict[str, tuple[int, int, float]] = {}  # iface -> (rx, tx, ts)


def _read(path: str) -> str:
    with open(path, "r") as f:
        return f.read()


def _cpu_pct() -> float:
    """Delta-based CPU utilization. Returns 0 on first call (no baseline yet)."""
    global _prev_cpu
    line = _read(f"{_PROC}/stat").splitlines()[0]  # "cpu  u n s i iow irq sirq st g gn"
    parts = [int(x) for x in line.split()[1:]]
    idle = parts[3] + (parts[4] if len(parts) > 4 else 0)
    total = sum(parts)
    pct = 0.0
    if _prev_cpu is not None:
        d_idle = idle - _prev_cpu[0]
        d_total = total - _prev_cpu[1]
        if d_total > 0:
            pct = 100.0 * (1.0 - d_idle / d_total)
    _prev_cpu = (idle, total)
    return round(max(0.0, min(100.0, pct)), 2)


def _mem() -> tuple[float, float, float]:
    """Returns (used_pct, used_mb, total_mb)."""
    vals: dict[str, int] = {}
    for line in _read(f"{_PROC}/meminfo").splitlines():
        k, _, rest = line.partition(":")
        vals[k.strip()] = int(rest.strip().split()[0])  # kB
    total = vals.get("MemTotal", 0)
    available = vals.get("MemAvailable", vals.get("MemFree", 0))
    used = max(0, total - available)
    pct = (100.0 * used / total) if total else 0.0
    return round(pct, 2), round(used / 1024, 1), round(total / 1024, 1)


def _load() -> float:
    return float(_read(f"{_PROC}/loadavg").split()[0])


def _disk_root() -> tuple[float, float, float]:
    """Root filesystem usage (used_pct, used_gb, total_gb). Uses statvfs on /."""
    st = os.statvfs("/")
    total = st.f_blocks * st.f_frsize
    free = st.f_bavail * st.f_frsize
    used = total - free
    pct = (100.0 * used / total) if total else 0.0
    return round(pct, 2), round(used / 1e9, 1), round(total / 1e9, 1)


def _net_rates() -> Iterable[tuple[str, float, float]]:
    """Per-iface Mbps in/out since last call. Skips loopback and docker bridges."""
    now = time.time()
    lines = _read(f"{_PROC}/net/dev").splitlines()[2:]
    for line in lines:
        iface, _, rest = line.partition(":")
        iface = iface.strip()
        if iface == "lo" or iface.startswith(("docker", "br-", "veth")):
            continue
        fields = rest.split()
        rx, tx = int(fields[0]), int(fields[8])
        prev = _prev_net.get(iface)
        _prev_net[iface] = (rx, tx, now)
        if prev is None:
            continue
        dt = now - prev[2]
        if dt <= 0:
            continue
        mbps_in = 8 * (rx - prev[0]) / dt / 1e6
        mbps_out = 8 * (tx - prev[1]) / dt / 1e6
        yield iface, round(max(0.0, mbps_in), 3), round(max(0.0, mbps_out), 3)


def _status(value: float, amber: float, red: float) -> str:
    if value >= red:
        return "red"
    if value >= amber:
        return "amber"
    return "green"


async def collect() -> list[Sample]:
    out: list[Sample] = []

    cpu = _cpu_pct()
    out.append(Sample("host", "cpu_pct", cpu, _status(cpu, 75, 90)))

    mem_pct, mem_used, mem_total = _mem()
    out.append(
        Sample(
            "host",
            "mem_pct",
            mem_pct,
            _status(mem_pct, 80, 92),
            labels={"used_mb": str(mem_used), "total_mb": str(mem_total)},
        )
    )

    out.append(Sample("host", "load_1m", _load()))

    disk_pct, disk_used, disk_total = _disk_root()
    out.append(
        Sample(
            "host",
            "disk_pct",
            disk_pct,
            _status(disk_pct, 80, 92),
            labels={"used_gb": str(disk_used), "total_gb": str(disk_total), "mount": "/"},
        )
    )

    for iface, mbps_in, mbps_out in _net_rates():
        out.append(Sample("host", "net_in_mbps", mbps_in, labels={"iface": iface}))
        out.append(Sample("host", "net_out_mbps", mbps_out, labels={"iface": iface}))

    return out
