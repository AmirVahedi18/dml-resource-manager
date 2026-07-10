"""JWT issuing/verification for the web API. Configured once at process startup via `configure()`."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

import jwt

ALGORITHM = "HS256"


@dataclass
class _Settings:
    secret: str
    expire_minutes: int


_settings: _Settings | None = None


def configure(secret: str, expire_minutes: int) -> None:
    global _settings
    _settings = _Settings(secret=secret, expire_minutes=expire_minutes)


def _require_settings() -> _Settings:
    if _settings is None:
        raise RuntimeError("dml_web.security.configure() must be called before issuing/verifying tokens")
    return _settings


def create_access_token(user_id: int) -> str:
    settings = _require_settings()
    now = datetime.now(timezone.utc)
    payload = {"sub": str(user_id), "iat": now, "exp": now + timedelta(minutes=settings.expire_minutes)}
    return jwt.encode(payload, settings.secret, algorithm=ALGORITHM)


def decode_user_id(token: str) -> int:
    """Raises a jwt.PyJWTError subclass for an invalid/expired token -- callers (see deps.py)
    catch that and turn it into a 401."""
    settings = _require_settings()
    payload = jwt.decode(token, settings.secret, algorithms=[ALGORITHM])
    return int(payload["sub"])
