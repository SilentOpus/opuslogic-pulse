#!/usr/bin/env bash
# Deploy OpusLogic Pulse on the VPS. Assumes the opuslogic_default Docker network
# already exists (created by the main platform's compose). Reads PULSE_* values
# from ../.env which should be created from .env.example.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$REPO_DIR"

if [[ ! -f .env ]]; then
  echo "missing .env — copy .env.example and fill in PULSE_POSTGRES_DSN" >&2
  exit 1
fi

if [[ ! -f infra/htpasswd ]]; then
  echo "missing infra/htpasswd — run: ./scripts/make-htpasswd.sh <user> <password>" >&2
  exit 1
fi

if ! docker network inspect opuslogic_default >/dev/null 2>&1; then
  echo "opuslogic_default network not found — start the main platform first" >&2
  exit 1
fi

docker compose -f infra/docker-compose.yml --env-file .env up -d --build
docker compose -f infra/docker-compose.yml ps
