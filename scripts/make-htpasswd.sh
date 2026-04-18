#!/usr/bin/env bash
# Generate or rotate the htpasswd file that protects Pulse behind basic auth.
# Uses openssl instead of the htpasswd binary so there's no extra dep.
set -euo pipefail

REPO_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="$REPO_DIR/infra/htpasswd"

USER="${1:-}"
PASS="${2:-}"
if [[ -z "$USER" || -z "$PASS" ]]; then
  echo "usage: $0 <user> <password>" >&2
  exit 1
fi

# Apache-compatible APR1 hash
SALT="$(openssl rand -base64 6 | tr -d '=+/' | head -c 8)"
HASH="$(openssl passwd -apr1 -salt "$SALT" "$PASS")"

mkdir -p "$(dirname "$OUT")"
echo "${USER}:${HASH}" > "$OUT"
chmod 640 "$OUT"
echo "wrote $OUT"
