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
import time
from collections import defaultdict, deque
from collections.abc import Iterable
from datetime import UTC, datetime, timedelta

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select

from .config import get_settings
from .db import clinicians, fetch_one, get_engine, get_session, revoked_tokens, utcnow

VALID_ROLES = {"clinician", "administrator", "auditor", "system"}

_bearer = HTTPBearer(auto_error=False)

# Prototype seed users. Passwords are development defaults; change via
# MEDIQUEUE_SEED_PASSWORD_* env vars before any shared deployment.
SEED_USERS = [
    ("clinician1", "clinician", "clinician1-pass"),
    ("admin", "administrator", "admin-pass"),
    ("auditor1", "auditor", "auditor-pass"),
]


_login_failures: dict[str, deque[float]] = defaultdict(deque)


def _throttle_key(client_ip: str, username: str) -> str:
    return f"{client_ip}|{username.lower()}"


def check_login_allowed(client_ip: str, username: str) -> int:
    """Return 0 if allowed, else seconds to wait (too many recent failures)."""
    s = get_settings()
    q = _login_failures[_throttle_key(client_ip, username)]
    now = time.monotonic()
    while q and now - q[0] > s.login_window_seconds:
        q.popleft()
    if len(q) >= s.login_max_attempts:
        return max(1, int(s.login_window_seconds - (now - q[0])))
    return 0


def record_login_failure(client_ip: str, username: str) -> None:
    _login_failures[_throttle_key(client_ip, username)].append(time.monotonic())


def clear_login_failures(client_ip: str, username: str) -> None:
    _login_failures.pop(_throttle_key(client_ip, username), None)


def reset_login_throttle() -> None:
    _login_failures.clear()


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
        "jti": secrets.token_hex(16),
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
        exp = exp.replace(tzinfo=UTC)
    if exp < utcnow():
        return None
    jti = payload.get("jti")
    if not jti or is_revoked(jti):
        return None
    return payload


def is_revoked(jti: str) -> bool:
    with get_engine().connect() as conn:
        return conn.execute(
            select(revoked_tokens.c.jti).where(revoked_tokens.c.jti == jti)
        ).first() is not None


def revoke_token(payload: dict) -> None:
    """Server-side logout: denylist the token id until it would expire anyway."""
    now = utcnow()
    exp = datetime.fromisoformat(payload["exp"])
    if exp.tzinfo is None:
        exp = exp.replace(tzinfo=UTC)
    with get_engine().begin() as conn:
        conn.execute(revoked_tokens.delete().where(revoked_tokens.c.exp < now))  # purge expired
        if not is_revoked(payload["jti"]):
            conn.execute(
                revoked_tokens.insert().values(jti=payload["jti"], exp=exp, revoked_at=now)
            )


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
        return {"username": payload["sub"], "role": role, "token": payload}
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
