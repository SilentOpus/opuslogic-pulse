"""Zitadel OIDC bearer-token validation for the Pulse collector API.

Mirrors the main platform's JWT verification pattern (common/security.py) so
Pulse reuses the same identity system. Required env:

    OIDC_ISSUER       e.g. https://auth.opuslogic.eu  (may omit trailing slash)
    OIDC_JWKS_URI     e.g. http://zitadel:8080/oauth/v2/keys  (container-local)
    OIDC_PROJECT_ID   Zitadel project-id / audience the tokens are minted for

Pulse requires callers hold the `platform.read` scope (via viewer+ roles).
"""
from __future__ import annotations

import logging
import os
from typing import Optional

import jwt
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import PyJWKClient

log = logging.getLogger("pulse.auth")

ROLE_SCOPES: dict[str, set[str]] = {
    "viewer": {"platform.read"},
    "operator": {"platform.read", "platform.write"},
    "tenant-admin": {"platform.read", "platform.write", "admin.read"},
    "platform-admin": {"platform.read", "platform.write", "admin.read", "admin.write"},
    "compliance-officer": {"platform.read"},
}
ZITADEL_ROLES_CLAIM = "urn:zitadel:iam:org:project:roles"
REQUIRED_SCOPE = "platform.read"

_jwks: PyJWKClient | None = None
bearer_scheme = HTTPBearer(auto_error=False)


def _jwks_client() -> PyJWKClient:
    global _jwks
    if _jwks is None:
        uri = os.environ.get("OIDC_JWKS_URI") or \
            f"{os.environ['OIDC_ISSUER'].rstrip('/')}/oauth/v2/keys"
        _jwks = PyJWKClient(uri, cache_keys=True, lifespan=3600)
    return _jwks


def _decode(token: str) -> dict:
    audience = os.environ["OIDC_PROJECT_ID"]
    issuer = os.environ.get("OIDC_ISSUER", "").rstrip("/")
    try:
        key = _jwks_client().get_signing_key_from_jwt(token).key
    except Exception as e:
        log.warning("jwks fetch failed: %s", e)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="token key fetch failed")
    opts: dict = {"algorithms": ["RS256"], "audience": audience}
    if issuer:
        opts["issuer"] = issuer
    try:
        return jwt.decode(token, key, **opts)
    except jwt.InvalidTokenError as e:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail=f"invalid token: {e}")


def _scopes_for(claims: dict) -> set[str]:
    roles = claims.get(ZITADEL_ROLES_CLAIM) or {}
    out: set[str] = set()
    for role in roles.keys() if isinstance(roles, dict) else []:
        out.update(ROLE_SCOPES.get(role, set()))
    return out


def _require(claims: dict) -> None:
    if REQUIRED_SCOPE not in _scopes_for(claims):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"missing scope {REQUIRED_SCOPE}",
        )


async def require_user(
    creds: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
) -> dict:
    """Dependency for HTTP endpoints. Returns the decoded JWT claims."""
    if creds is None or creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bearer token required")
    claims = _decode(creds.credentials)
    _require(claims)
    return claims


async def verify_token_string(token: str) -> dict:
    """For WebSocket auth — caller passes the raw token from query/cookie."""
    claims = _decode(token)
    _require(claims)
    return claims


def auth_required() -> bool:
    """Auth can be disabled locally via PULSE_AUTH_DISABLED=1 for dev runs."""
    return os.environ.get("PULSE_AUTH_DISABLED", "") not in ("1", "true", "yes")
