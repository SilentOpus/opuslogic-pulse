"""Platform-security posture probe — R10.1-PLAT.

Continuously evaluates the hardening-finding states from
`automation-platform/docs/hardening-audit-2026-04.md`. Audience: OpusLogic
ops / engineering, not customers. The customer compliance scorecard is a
separate surface (see audit §R10.4-CUST) and deliberately never mixes with
platform posture.

Each check returns a Sample with status ∈ {green, amber, red} plus a
compact `message` that says what's wrong when it's not green.

Design constraints:
  * Fail-safe. A check that can't run (missing mount, unreachable target)
    returns `unknown` with a reason — never crashes the probe loop.
  * Read-only. No probe ever writes to the platform DB or filesystem.
  * Minimal container surface. Bind-mounts are optional; checks gated on
    path existence so the probe is safe to deploy before Pulse's compose
    learns the new mounts.

Configurable via env:
  PULSE_PLATFORM_HOST_ROOT   Default: /host
                             Pulse container bind-mount root for the host
                             filesystem (so /host/opt/backups, /host/etc,
                             /host/opt/opuslogic/.env are reachable).
  PULSE_PLATFORM_URL         Default: https://opuslogic_caddy/
                             Base URL to probe ingress surface.
"""

from __future__ import annotations

import asyncio
import logging
import os
import ssl
import time
from datetime import datetime, timezone
from pathlib import Path

import httpx
import psycopg

from . import Sample

log = logging.getLogger("pulse.probes.security")
name = "security"

_HOST_ROOT = os.getenv("PULSE_PLATFORM_HOST_ROOT", "/host")
_PLATFORM_URL = os.getenv("PULSE_PLATFORM_URL", "https://dev.opuslogic.eu")

# Probe-level thresholds. Over here rather than in config so they're easy
# to tune without bouncing the whole collector.
_BACKUP_FRESHNESS_AMBER_SEC = 3600 * 25    # ≥ 25h old = amber
_BACKUP_FRESHNESS_RED_SEC = 3600 * 48      # ≥ 48h old = red
_TLS_CERT_AMBER_DAYS = 30
_TLS_CERT_RED_DAYS = 7
_ENCRYPT_COVERAGE_RED_PCT = 100.0          # any plaintext row = red
_ENCRYPT_COVERAGE_AMBER_PCT = 100.0        # binary — either clean or not

# ── Individual checks ───────────────────────────────────────────────────

def _check_backup_freshness() -> Sample:
    """Newest hourly dump should be less than 25h old on a healthy cron."""
    backup_dir = Path(_HOST_ROOT) / "opt" / "backups" / "hourly"
    if not backup_dir.exists():
        return Sample(
            name, "backup_freshness", -1,
            status="unknown",
            message=f"path {backup_dir} not visible — bind-mount /opt/backups?",
        )
    dumps = sorted(backup_dir.glob("*.sql.age"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not dumps:
        return Sample(
            name, "backup_freshness", -1,
            status="red",
            message="no dumps in /opt/backups/hourly",
        )
    newest = dumps[0]
    age_sec = time.time() - newest.stat().st_mtime
    age_hours = round(age_sec / 3600, 2)
    if age_sec >= _BACKUP_FRESHNESS_RED_SEC:
        status, msg = "red", f"oldest newest dump is {age_hours}h old — cron broken?"
    elif age_sec >= _BACKUP_FRESHNESS_AMBER_SEC:
        status, msg = "amber", f"newest dump is {age_hours}h old (expected <25h)"
    else:
        status, msg = "green", ""
    return Sample(name, "backup_freshness_hours", age_hours, status=status,
                  labels={"newest": newest.name}, message=msg)


def _check_env_file_mode() -> Sample:
    """/.env must be mode 600 so non-root users on the host can't read
    secrets. Audit finding R1.1."""
    env_path = Path(_HOST_ROOT) / "opt" / "opuslogic" / ".env"
    if not env_path.exists():
        return Sample(name, "env_file_mode", -1, status="unknown",
                      message=f".env not visible — bind-mount /opt/opuslogic?")
    mode = env_path.stat().st_mode & 0o777
    mode_oct = oct(mode)
    if mode == 0o600:
        return Sample(name, "env_file_mode_ok", 1, status="green",
                      labels={"mode": mode_oct})
    return Sample(name, "env_file_mode_ok", 0, status="red",
                  labels={"mode": mode_oct},
                  message=f".env mode is {mode_oct}; expected 0600")


def _check_encryption_key_file_mode() -> Sample:
    """/etc/opuslogic/secrets/encryption-key must be mode 400 UID 1000.
    Audit finding R1.3."""
    path = Path(_HOST_ROOT) / "etc" / "opuslogic" / "secrets" / "encryption-key"
    if not path.exists():
        return Sample(name, "encryption_key_file", -1, status="unknown",
                      message="encryption-key not visible — bind-mount /etc/opuslogic?")
    st = path.stat()
    mode = st.st_mode & 0o777
    ok = mode == 0o400 and st.st_uid == 1000 and st.st_gid == 1000
    status = "green" if ok else "red"
    msg = "" if ok else f"mode={oct(mode)} uid={st.st_uid} gid={st.st_gid}; expected 400 1000:1000"
    return Sample(name, "encryption_key_file_ok", 1 if ok else 0, status=status,
                  labels={"mode": oct(mode), "uid": str(st.st_uid)}, message=msg)


async def _check_credential_encryption_coverage() -> Sample:
    """Count credential rows still in plaintext (credential_user_inputs
    populated AND credential_encrypted NULL). Should be 0 after R1.3
    Step 5. Audit finding R1.3."""
    dsn = os.environ.get("PULSE_POSTGRES_DSN", "")
    if not dsn:
        return Sample(name, "credential_plaintext_rows", -1, status="unknown",
                      message="PULSE_POSTGRES_DSN not configured")

    def _q() -> tuple[int, int]:
        with psycopg.connect(dsn, connect_timeout=3) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    "SELECT "
                    "  count(*) FILTER (WHERE credential_user_inputs IS NOT NULL "
                    "                    AND credential_encrypted IS NULL "
                    "                    AND credential_is_folder = 0), "
                    "  count(*) FILTER (WHERE credential_is_folder = 0) "
                    "FROM credentials"
                )
                plain, total = cur.fetchone()
                return int(plain), int(total)

    try:
        plain, total = await asyncio.to_thread(_q)
    except Exception as e:
        return Sample(name, "credential_plaintext_rows", -1, status="unknown",
                      message=f"query failed: {str(e)[:100]}")

    status = "green" if plain == 0 else "red"
    msg = "" if plain == 0 else f"{plain} plaintext credential rows remain (expected 0)"
    return Sample(name, "credential_plaintext_rows", plain, status=status,
                  labels={"total": str(total)}, message=msg)


async def _check_public_temporal_ingress() -> Sample:
    """Verify /temporal/* is not publicly reachable — R8.1 was resolved,
    this probe detects regression (e.g. if someone re-adds the handler)."""
    url = f"{_PLATFORM_URL.rstrip('/')}/temporal/"
    try:
        async with httpx.AsyncClient(verify=False, timeout=3) as client:
            r = await client.get(url, follow_redirects=False)
    except Exception as e:
        return Sample(name, "public_temporal_ingress_open", -1, status="unknown",
                      message=f"probe failed: {str(e)[:100]}")
    # Any 2xx = Temporal UI is being served publicly. 401/403/404 = good.
    ok = r.status_code in (401, 403, 404)
    return Sample(name, "public_temporal_ingress_open", 0 if ok else 1,
                  status="green" if ok else "red",
                  labels={"http_status": str(r.status_code)},
                  message="" if ok else f"/temporal/ returns {r.status_code} — public regression")


async def _check_tls_cert_expiry() -> Sample:
    """Days until the public-facing TLS cert expires. Auto-renews via
    Caddy but we want an alert if renewal somehow stalls."""
    # Parse host/port out of PLATFORM_URL
    from urllib.parse import urlparse
    u = urlparse(_PLATFORM_URL)
    host = u.hostname or "dev.opuslogic.eu"
    port = u.port or (443 if u.scheme == "https" else 80)

    def _probe_cert() -> int:
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE  # we inspect not verify
        import socket
        with socket.create_connection((host, port), timeout=3) as sock:
            with ctx.wrap_socket(sock, server_hostname=host) as ssock:
                cert = ssock.getpeercert()
                # notAfter like 'Jul 14 12:00:00 2026 GMT'
                from datetime import datetime as _dt
                expiry = _dt.strptime(cert["notAfter"], "%b %d %H:%M:%S %Y %Z").replace(tzinfo=timezone.utc)
                return (expiry - datetime.now(timezone.utc)).days

    try:
        days = await asyncio.to_thread(_probe_cert)
    except Exception as e:
        return Sample(name, "tls_cert_days_remaining", -1, status="unknown",
                      message=f"probe failed: {str(e)[:100]}")

    if days < _TLS_CERT_RED_DAYS:
        status, msg = "red", f"cert expires in {days}d — renewal stalled?"
    elif days < _TLS_CERT_AMBER_DAYS:
        status, msg = "amber", f"cert expires in {days}d"
    else:
        status, msg = "green", ""
    return Sample(name, "tls_cert_days_remaining", days, status=status,
                  labels={"host": host}, message=msg)


async def _check_binary_signing_enabled() -> Sample:
    """Verify the agent's signing pubkey is not the empty placeholder.
    Checks via backend's download metadata — same path agents use.
    Audit finding R7.1."""
    url = f"{_PLATFORM_URL.rstrip('/')}/backend/agents/download/linux/amd64/version"
    try:
        async with httpx.AsyncClient(verify=False, timeout=3) as client:
            r = await client.get(url)
    except Exception as e:
        return Sample(name, "agent_binary_signed", -1, status="unknown",
                      message=f"probe failed: {str(e)[:100]}")
    if r.status_code != 200:
        return Sample(name, "agent_binary_signed", -1, status="unknown",
                      labels={"http_status": str(r.status_code)},
                      message=f"version endpoint returned {r.status_code}")
    try:
        data = r.json()
    except Exception:
        return Sample(name, "agent_binary_signed", -1, status="unknown",
                      message="version endpoint returned non-JSON")
    sig = data.get("signature_ed25519", "")
    ok = bool(sig)
    return Sample(name, "agent_binary_signed", 1 if ok else 0,
                  status="green" if ok else "red",
                  labels={"version": str(data.get("version", ""))},
                  message="" if ok else "latest agent binary has no ed25519 signature")


# ── Entry point ─────────────────────────────────────────────────────────

async def collect() -> list[Sample]:
    """Run all security checks in parallel (or fast sequential for
    filesystem ones). Returns a flat list of Samples. Any individual
    check that raises is caught upstream by _safe_collect in the
    scheduler — but each check here is internally try/except'd for
    more specific error messages."""
    fs_results: list[Sample] = [
        _check_backup_freshness(),
        _check_env_file_mode(),
        _check_encryption_key_file_mode(),
    ]
    http_results = await asyncio.gather(
        _check_credential_encryption_coverage(),
        _check_public_temporal_ingress(),
        _check_tls_cert_expiry(),
        _check_binary_signing_enabled(),
        return_exceptions=False,
    )
    return fs_results + list(http_results)
