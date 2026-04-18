#!/usr/bin/env bash
# Register the Pulse SPA in the existing OpusLogic Zitadel project.
#
# Reuses the platform's roles/project so existing users can log into Pulse
# without re-granting. Produces VITE_OIDC_CLIENT_ID and OIDC_PROJECT_ID values
# you paste into .env.
#
# Requires:
#   ZITADEL_URL        base URL, e.g. https://auth.opuslogic.eu
#   ZITADEL_PAT        personal access token for a user with IAM_OWNER or
#                      ORG_PROJECT_EDITOR on the OpusLogic project
#   PULSE_HOSTNAME     optional; defaults to pulse.opuslogic.eu
#
# Idempotent — re-running updates the redirect URIs rather than duplicating.
set -euo pipefail

: "${ZITADEL_URL:?set ZITADEL_URL, e.g. https://auth.opuslogic.eu}"
: "${ZITADEL_PAT:?set ZITADEL_PAT (personal access token)}"
PULSE_HOSTNAME="${PULSE_HOSTNAME:-pulse.opuslogic.eu}"
APP_NAME="pulse-frontend"
REDIRECT="https://${PULSE_HOSTNAME}"

zapi() {
    local method=$1 path=$2 body=${3:-}
    local args=(-sS -X "$method" -H "Authorization: Bearer $ZITADEL_PAT")
    if [[ -n "$body" ]]; then args+=(-H "Content-Type: application/json" -d "$body"); fi
    curl "${args[@]}" "${ZITADEL_URL%/}${path}"
}

echo "==> looking up OpusLogic project…"
PROJECT_ID=$(zapi POST "/management/v1/projects/_search" '{}' \
    | jq -r '.result[]? | select(.name=="OpusLogic") | .id' | head -1)
[[ -n "$PROJECT_ID" ]] || { echo "OpusLogic project not found — run the platform's setup-zitadel.sh first" >&2; exit 1; }
echo "    project_id=$PROJECT_ID"

APP_BODY=$(cat <<EOF
{
  "name": "${APP_NAME}",
  "redirectUris": ["${REDIRECT}", "${REDIRECT}/"],
  "postLogoutRedirectUris": ["${REDIRECT}"],
  "responseTypes": ["OIDC_RESPONSE_TYPE_CODE"],
  "grantTypes": ["OIDC_GRANT_TYPE_AUTHORIZATION_CODE"],
  "appType": "OIDC_APP_TYPE_USER_AGENT",
  "authMethodType": "OIDC_AUTH_METHOD_TYPE_NONE",
  "devMode": false,
  "accessTokenType": "OIDC_TOKEN_TYPE_JWT",
  "idTokenRoleAssertion": true,
  "accessTokenRoleAssertion": true
}
EOF
)

echo "==> registering/refreshing OIDC app '${APP_NAME}'…"
RESP=$(zapi POST "/management/v1/projects/$PROJECT_ID/apps/oidc" "$APP_BODY")
CLIENT_ID=$(echo "$RESP" | jq -r '.clientId // empty')
APP_ID=$(echo "$RESP" | jq -r '.appId // empty')

if [[ -z "$CLIENT_ID" ]]; then
    LIST=$(zapi POST "/management/v1/projects/$PROJECT_ID/apps/_search" '{}')
    CLIENT_ID=$(echo "$LIST" | jq -r ".result[]? | select(.name==\"${APP_NAME}\") | .oidcConfig.clientId" | head -1)
    APP_ID=$(echo "$LIST" | jq -r ".result[]? | select(.name==\"${APP_NAME}\") | .id" | head -1)
    [[ -n "$CLIENT_ID" ]] || { echo "create failed: $RESP" >&2; exit 1; }
    echo "    app already existed, refreshing config…"
    zapi PUT "/management/v1/projects/$PROJECT_ID/apps/$APP_ID/oidc" "$APP_BODY" >/dev/null
fi

echo
echo "==> Paste into .env on the VPS:"
echo "  VITE_OIDC_AUTHORITY=${ZITADEL_URL%/}"
echo "  VITE_OIDC_CLIENT_ID=${CLIENT_ID}"
echo "  OIDC_ISSUER=${ZITADEL_URL%/}"
echo "  OIDC_JWKS_URI=${ZITADEL_URL%/}/oauth/v2/keys"
echo "  OIDC_PROJECT_ID=${PROJECT_ID}"
