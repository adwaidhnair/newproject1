import hashlib
import hmac
import os
import secrets
import time
from typing import Optional

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError
from fastapi import Cookie, Depends, HTTPException
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.auth_models import OrganizationMembership, User

bearer_scheme = HTTPBearer(auto_error=False)
ACCESS_TOKEN_TTL_SECONDS = int(os.getenv("ACCESS_TOKEN_TTL_SECONDS", "3600"))
PASSWORD_ITERATIONS = int(os.getenv("PASSWORD_HASH_ITERATIONS", "310000"))
ROLE_LEVEL = {"viewer": 10, "analyst": 20, "admin": 30, "owner": 40}
SESSION_COOKIE_NAME = "erp_intel_session"
LOGIN_WINDOW_SECONDS = int(os.getenv("LOGIN_RATE_WINDOW_SECONDS", "900"))
LOGIN_MAX_ATTEMPTS = int(os.getenv("LOGIN_RATE_MAX_ATTEMPTS", "10"))
password_hasher = PasswordHasher()


def _token_secret() -> str:
    secret = os.getenv("AUTH_TOKEN_SECRET")
    if not secret and os.getenv("ENVIRONMENT", "development").lower() not in {"production", "prod"}:
        return "development-only-change-me"
    if not secret:
        raise HTTPException(status_code=503, detail="Authentication is not configured")
    return secret


def hash_password(password: str) -> str:
    return password_hasher.hash(password)


def verify_password(password: str, encoded: str) -> bool:
    if encoded.startswith("$argon2"):
        try:
            return password_hasher.verify(encoded, password)
        except (InvalidHashError, VerificationError, TypeError):
            return False
    try:
        algorithm, iterations, salt_hex, digest_hex = encoded.split("$", 3)
        if algorithm != "pbkdf2_sha256" or not 100_000 <= int(iterations) <= 2_000_000:
            return False
        digest = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt_hex), int(iterations))
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


def password_needs_rehash(encoded: str) -> bool:
    if not encoded.startswith("$argon2"):
        return True
    try:
        return password_hasher.check_needs_rehash(encoded)
    except (InvalidHashError, TypeError):
        return True


def validate_token_secret() -> None:
    secret = os.getenv("AUTH_TOKEN_SECRET")
    if os.getenv("ENVIRONMENT", "development").lower() in {"production", "prod"}:
        if not secret or len(secret) < 32:
            raise RuntimeError("AUTH_TOKEN_SECRET must be configured with at least 32 characters")
    setup_token = os.getenv("BOOTSTRAP_SETUP_TOKEN")
    if setup_token and len(setup_token) < 32:
        raise RuntimeError("BOOTSTRAP_SETUP_TOKEN must contain at least 32 characters")
    if not 100_000 <= PASSWORD_ITERATIONS <= 2_000_000:
        raise RuntimeError("PASSWORD_HASH_ITERATIONS must be between 100000 and 2000000")
    if LOGIN_WINDOW_SECONDS < 60 or LOGIN_MAX_ATTEMPTS < 1:
        raise RuntimeError("Login rate-limit settings are invalid")


def issue_access_token(user_id: str, auth_version: int = 0) -> str:
    issued = str(int(time.time()))
    nonce = secrets.token_urlsafe(12)
    payload = f"{user_id}.{issued}.{auth_version}.{nonce}"
    signature = hmac.new(_token_secret().encode(), payload.encode(), hashlib.sha256).hexdigest()
    return f"{payload}.{signature}"


def get_current_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(bearer_scheme),
    session_cookie: Optional[str] = Cookie(default=None, alias=SESSION_COOKIE_NAME),
    db: Session = Depends(get_db),
) -> User:
    token = credentials.credentials if credentials and credentials.scheme.lower() == "bearer" else session_cookie
    if not token:
        raise HTTPException(status_code=401, detail="Bearer access token required", headers={"WWW-Authenticate": "Bearer"})
    try:
        user_id, issued, auth_version, nonce, signature = token.rsplit(".", 4)
        secret = _token_secret()
        payload = f"{user_id}.{issued}.{auth_version}.{nonce}"
        expected = hmac.new(secret.encode(), payload.encode(), hashlib.sha256).hexdigest()
        age = int(time.time()) - int(issued)
        token_version = int(auth_version)
    except (ValueError, TypeError):
        raise HTTPException(status_code=401, detail="Invalid access token")
    if not hmac.compare_digest(signature, expected) or age < 0 or age > ACCESS_TOKEN_TTL_SECONDS:
        raise HTTPException(status_code=401, detail="Invalid or expired access token")
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True)).one_or_none()
    if user is None or user.auth_version != token_version:
        raise HTTPException(status_code=401, detail="User is inactive or no longer exists")
    return user


def require_org_access(db: Session, user: User, org_id: str, minimum_role: str = "viewer") -> str:
    membership = (
        db.query(OrganizationMembership)
        .filter(OrganizationMembership.user_id == user.id, OrganizationMembership.org_id == org_id)
        .one_or_none()
    )
    if membership is None or ROLE_LEVEL.get(membership.role, 0) < ROLE_LEVEL[minimum_role]:
        raise HTTPException(status_code=403, detail="User is not authorized for this organization")
    return membership.role
