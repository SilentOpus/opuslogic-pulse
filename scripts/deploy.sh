#!/usr/bin/env bash
# Deploy OpusLogic Pulse on the VPS. Assumes the opuslogic_default Docker
# network already exists (created by the main platform's compose) and that
# pulse.opuslogic.eu DNS resolves to this host so Caddy can fetch a Let's
# Encrypt cert on startup.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if [[ ! -f .env ]]; then
    echo "missing .env — copy .env.example and fill in the OIDC + Postgres values" >&2
    exit 1
fi

if ! docker network inspect opuslogic_default >/dev/null 2>&1; then
    echo "opuslogic_default network not found — start the main platform first" >&2
    exit 1
fi

# Sanity-check ports. Caddy binds 80/443 on the host.
if ss -ltn 2>/dev/null | awk '{print $4}' | grep -qE ':(80|443)$'; then
    echo "WARN: something already listens on :80 or :443 — Caddy may fail to bind" >&2
fi

docker compose -f infra/docker-compose.yml --env-file .env up -d --build
docker compose -f infra/docker-compose.yml ps
