"""
Authentication middleware and utilities for Supabase JWT verification.
Supabase Auth issues ES256 JWTs; we verify via JWKS.
"""
import os
import time
from typing import Optional

import httpx
from dotenv import load_dotenv
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import jwt, jwk
from jose.exceptions import JWTError, ExpiredSignatureError
from pathlib import Path

# Load .env
env_path = Path(__file__).resolve().parent.parent / ".env"
if env_path.exists():
    load_dotenv(env_path)
else:
    load_dotenv()

SUPABASE_URL = (os.getenv("SUPABASE_URL") or os.getenv("VITE_SUPABASE_URL") or "").rstrip("/")
if not SUPABASE_URL:
    raise RuntimeError(
        "SUPABASE_URL (or VITE_SUPABASE_URL) is not set. "
        "Configure it in your environment or `.env` file."
    )

JWKS_URL = f"{SUPABASE_URL}/auth/v1/.well-known/jwks.json"

# In-memory cache: { "keys": [...], "fetched_at": unix_ts }
_jwks_cache: Optional[dict] = None
_JWKS_MAX_AGE = 300  # seconds


def _fetch_jwks() -> dict:
    global _jwks_cache
    now = time.time()
    if _jwks_cache and (now - _jwks_cache.get("fetched_at", 0)) < _JWKS_MAX_AGE:
        return _jwks_cache["keys"]
    with httpx.Client(timeout=10) as client:
        r = client.get(JWKS_URL)
        r.raise_for_status()
        data = r.json()
    keys = data.get("keys") or []
    _jwks_cache = {"keys": keys, "fetched_at": now}
    return keys


def _get_key_for_token(token: str):
    """Get JWK for the token's kid from JWKS."""
    try:
        unverified = jwt.get_unverified_header(token)
    except Exception:
        return None
    kid = unverified.get("kid")
    if not kid:
        return None
    keys = _fetch_jwks()
    for k in keys:
        if k.get("kid") == kid:
            return jwk.construct(k)
    return None


def verify_supabase_jwt(token: str) -> Optional[dict]:
    """
    Verify Supabase JWT (ES256) via JWKS and return payload if valid.
    """
    try:
        key = _get_key_for_token(token)
        if not key:
            print("[JWT Verify] No matching JWK for token kid")
            return None
        payload = jwt.decode(
            token,
            key,
            algorithms=["ES256"],
            options={"verify_signature": True, "verify_exp": True, "verify_aud": False},
        )
        return payload
    except ExpiredSignatureError as e:
        print(f"[JWT Verify] Token expired: {e}")
        return None
    except JWTError as e:
        print(f"[JWT Verify] Invalid token: {e}")
        return None
    except Exception as e:
        print(f"[JWT Verify] Unexpected error: {type(e).__name__}: {e}")
        import traceback
        traceback.print_exc()
        return None


security = HTTPBearer()


async def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> dict:
    token = credentials.credentials
    payload = verify_supabase_jwt(token)
    if payload is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return payload
