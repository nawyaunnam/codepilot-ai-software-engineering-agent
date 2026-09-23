"""Single-operator authentication. No anonymous access or default credentials."""

import hashlib
import hmac
import time
from datetime import datetime, timedelta, timezone
from threading import Lock

from fastapi import HTTPException, Request
from jose import JWTError, jwt

from .config import settings

_attempts = {}
_lock = Lock()


def login(username, password, ip):
    with _lock:
        now = time.monotonic()
        # Bounded process-local limit; deploy an ingress limit across API replicas.
        for key in list(_attempts):
            if now - _attempts[key][0] > 60:
                del _attempts[key]
        start, count = _attempts.get(ip, (now, 0))
        if count >= 5 or len(_attempts) >= 10000:
            raise HTTPException(429, "Too many login attempts; retry in one minute")
        _attempts[ip] = (start, count + 1)
    if not settings.admin_password or len(settings.jwt_secret) < 32:
        raise HTTPException(503, "Configure ADMIN_PASSWORD and a JWT_SECRET of at least 32 characters")
    valid = hmac.compare_digest(
        hashlib.sha256(password.encode()).digest(), hashlib.sha256(settings.admin_password.encode()).digest()
    )
    if not valid or username != settings.admin_username:
        raise HTTPException(401, "Invalid credentials")
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {
            "sub": username,
            "iat": now,
            "exp": now + timedelta(hours=1),
            "iss": "codepilot",
            "aud": "codepilot",
        },
        settings.jwt_secret,
        algorithm="HS256",
    )


def require_user(request: Request):
    header = request.headers.get("authorization", "")
    token = header[7:] if header.startswith("Bearer ") else request.cookies.get("codepilot_session")
    if not token or len(settings.jwt_secret) < 32:
        raise HTTPException(401, "Sign in required")
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=["HS256"],
            issuer="codepilot",
            audience="codepilot",
            options={"require_exp": True, "require_sub": True},
        )
        if claims["sub"] != settings.admin_username:
            raise JWTError("Unknown operator")
    except JWTError as exc:
        raise HTTPException(401, "Invalid or expired session") from exc
    # SameSite strict + explicit Origin check for browser mutations.
    if not header and request.method not in {"GET", "HEAD"}:
        origin = request.headers.get("origin")
        if origin and origin not in settings.allowed_origins.split(","):
            raise HTTPException(403, "Origin not allowed")
    return claims["sub"]
