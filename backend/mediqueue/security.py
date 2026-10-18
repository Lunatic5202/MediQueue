"""Authentication and role-based access (prototype-grade).

Basic auth and login endpoints issue an HMAC-signed bearer token. Full
identity-provider integration is a production target (see docs/security notes
in README and IBM Z deployment document).
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import secrets
from datetime import datetime, timedelta, timezone
from typing import Iterable

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from .config import get_settings
from .db import clinicians, fetch_one, get_engine, get_session, utcnow

VALID_ROLES = {"clinician", "administrator", "auditor", "system"}

_bearer = HTTPBearer(auto_error=False)

# Prototype seed users. Passwords are development defaults; change via
# MEDIQUEUE_SEED_PASSWORD_* env vars before any shared deployment.
SEED_USERS = [
    ("clinician1", "clinician", "clinician1-pass"),
    ("admin", "administrator", "admin-pass"),
    ("auditor1", "auditor", "auditor-pass"),
]


def hash_password(password: str, salt: str) -> str:
    dk = hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), iterations=120_000
    )
    return dk.hex()


def ensure_seed_users() -> None:
    import os

    env_map = {
        "clinician1": os.environ.get("MEDIQUEUE_SEED_PASSWORD_CLINICIAN", "clinician1-pass"),
        "admin": os.environ.get("MEDIQUEUE_SEED_PASSWORD_ADMIN", "admin-pass"),
        "auditor1": os.environ.get("MEDIQUEUE_SEED_PASSWORD_AUDITOR", "auditor-pass"),
    }
    with get_engine().begin() as conn:
        for username, role, default_pw in SEED_USERS:
            existing = fetch_one(conn, select(clinicians).where(clinicians.c.username == username))
            if existing:
                continue
            password = env_map.get(username, default_pw)
            salt = secrets.token_hex(16)
            conn.execute(
                clinicians.insert().values(
                    username=username,
                    role=role,
                    password_hash=hash_password(password, salt),
                    salt=salt,
                    created_at=utcnow(),
                )
            )


def verify_credentials(username: str, password: str) -> dict | None:
    with get_session() as session:
        row = session.execute(
            select(clinicians).where(clinicians.c.username == username)
        ).mappings().first()
        if not row:
            return None
        candidate = hash_password(password, row["salt"])
        if not hmac.compare_digest(candidate, row["password_hash"]):
            return None
        return {"username": row["username"], "role": row["role"]}


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    padding = "=" * (-len(data) % 4)
    return base64.urlsafe_b64decode(data + padding)


def issue_token(username: str, role: str) -> tuple[str, datetime]:
    settings = get_settings()
    expires = utcnow() + timedelta(seconds=settings.token_ttl_seconds)
    payload = {
        "sub": username,
        "role": role,
        "exp": expires.isoformat(),
        "iat": utcnow().isoformat(),
    }
    body = _b64url(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    sig = hmac.new(settings.secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256).digest()
    return f"{body}.{_b64url(sig)}", expires


def decode_token(token: str) -> dict | None:
    settings = get_settings()
    try:
        body, sig = token.split(".", 1)
    except ValueError:
        return None
    expected = hmac.new(
        settings.secret_key.encode("utf-8"), body.encode("ascii"), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(_b64url(expected), sig):
        return None
    try:
        payload = json.loads(_b64url_decode(body))
    except (ValueError, json.JSONDecodeError):
        return None
    exp_raw = payload.get("exp")
    if not exp_raw:
        return None
    exp = datetime.fromisoformat(exp_raw)
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=timezone.utc)
    if exp < utcnow():
        return None
    return payload


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": "Bearer, Basic"},
    )


async def current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
) -> dict:
    """Resolve the acting user from a Bearer token (issued by /api/auth/login).

    HTTP Basic is accepted at the login endpoint only; production deployments
    should front the service with the institutional identity provider.
    """
    if credentials is not None:
        payload = decode_token(credentials.credentials)
        if payload is None:
            raise _unauthorized("Invalid or expired token")
        role = payload.get("role")
        if role not in VALID_ROLES:
            raise _unauthorized("Invalid role")
        return {"username": payload["sub"], "role": role}
    raise _unauthorized("Authentication required")


def require_roles(roles: Iterable[str]):
    allowed = set(roles)

    async def _dep(user: dict = Depends(current_user)) -> dict:
        if user["role"] not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Requires role in {sorted(allowed)}",
            )
        return user

    return _dep


# Role helpers used across routes
ClinicianUser = require_roles({"clinician", "administrator"})
AuditorUser = require_roles({"auditor", "administrator", "clinician"})
AdminUser = require_roles({"administrator"})
ReplayOperator = require_roles({"clinician", "administrator"})
