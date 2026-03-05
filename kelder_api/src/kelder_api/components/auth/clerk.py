import logging
from functools import lru_cache

import jwt
from jwt import PyJWKClient
from fastapi import Request

from src.kelder_api.configuration.settings import get_settings

logger = logging.getLogger("api.auth")


@lru_cache(maxsize=1)
def _get_jwks_client():
    url = get_settings().clerk.jwks_url
    return PyJWKClient(url) if url else None


def get_optional_user_id(request: Request) -> str:
    """Extract Clerk user_id from Bearer JWT. Returns 'anonymous' on missing/invalid token."""
    auth = request.headers.get("Authorization", "")
    if not auth.startswith("Bearer "):
        return "anonymous"
    token = auth[7:]
    client = _get_jwks_client()
    try:
        if client:
            signing_key = client.get_signing_key_from_jwt(token)
            claims = jwt.decode(token, signing_key.key, algorithms=["RS256"])
        else:
            # Dev mode — no JWKS configured; decode without verification
            claims = jwt.decode(token, options={"verify_signature": False})
        return claims.get("sub", "anonymous")
    except Exception:
        logger.warning("JWT extraction failed — using anonymous")
        return "anonymous"
