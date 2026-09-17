from __future__ import annotations

import bcrypt as _bcrypt
import os
from datetime import datetime, timedelta
from typing import Optional

import jwt
from pydantic import BaseModel

# ── JWT Configuration ─────────────────────────────────────────────────────────
_PLACEHOLDER = "your-secret-key-change-in-production"
SECRET_KEY = os.getenv("SECRET_KEY", _PLACEHOLDER)

# Checked at API startup (service/api.py startup event).
# Kept importable here so seed_users.py can use hash_password without JWT.
SECRET_KEY_VALID = SECRET_KEY != _PLACEHOLDER and len(SECRET_KEY) >= 32

ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 30

# Single source of truth for the session cookie's Max-Age. The cookie and the
# JWT must expire together: a cookie that outlives the token leaves the browser
# sending a credential the API rejects, and a cookie that dies first logs the
# user out while their token is still valid.
ACCESS_TOKEN_EXPIRE_SECONDS = ACCESS_TOKEN_EXPIRE_MINUTES * 60

# Renew an active session once it is this close to expiry. Comfortably shorter
# than the token lifetime so a heartbeat that misses a beat still has room, and
# long enough that an idle tab is not kept alive indefinitely.
SESSION_RENEW_THRESHOLD_SECONDS = ACCESS_TOKEN_EXPIRE_SECONDS // 3


# ── Password hashing (direct bcrypt — no passlib dependency) ──────────────────

def hash_password(password: str) -> str:
    return _bcrypt.hashpw(
        password.encode("utf-8"),
        _bcrypt.gensalt(),
    ).decode("utf-8")


def verify_password(plain_password: str, hashed_password: str) -> bool:
    try:
        return _bcrypt.checkpw(
            plain_password.encode("utf-8"),
            hashed_password.encode("utf-8"),
        )
    except Exception:
        return False


# ── JWT ───────────────────────────────────────────────────────────────────────

class TokenPayload(BaseModel):
    sub: str        # user UUID
    role: str       # sourcer | recruiter | admin
    email: str
    exp: datetime
    iat: datetime
    iss: str = "cv-pipeline-api"


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    to_encode = data.copy()
    expire = (
        datetime.utcnow() + expires_delta
        if expires_delta
        else datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "iat": datetime.utcnow(), "iss": "cv-pipeline-api"})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[TokenPayload]:
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        return TokenPayload(**payload)
    except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):
        return None
