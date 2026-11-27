import os
import secrets
from typing import Optional

from fastapi import Header, HTTPException
from sqlalchemy.orm import Session

from app.core.auth import require_org_access
from app.models.auth_models import User
from app.models.erp_models import Organization


def require_api_key(
    db: Session,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
):
    # Production requests use user-issued bearer tokens. Keep API-key auth for
    # existing integrations, but never treat it as a human identity.
    if authorization and authorization.lower().startswith("bearer "):
        try:
            return get_current_user_from_token(authorization[7:].strip(), db)
        except HTTPException:
            raise
    expected_key = get_configured_api_key()
    if expected_key is None and os.getenv("ENVIRONMENT", "development").lower() not in {"production", "prod"}:
        return
    supplied_key = x_api_key
    if expected_key is None or supplied_key is None or not secrets.compare_digest(supplied_key, expected_key):
        raise HTTPException(status_code=401, detail="Valid bearer token or API key required")


def resolve_tenant(
    org_id: str,
    db: Session,
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
):
    user = None
    if authorization and authorization.lower().startswith("bearer "):
        user = get_current_user_from_token(authorization[7:].strip(), db)
    else:
        require_api_key(authorization, x_api_key, db)
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    if user is not None:
        require_org_access(db, user, org_id)
    return org_id


def get_current_user_from_token(token: str, db: Session) -> User:
    from fastapi.security import HTTPAuthorizationCredentials
    from app.core.auth import get_current_user

    return get_current_user(HTTPAuthorizationCredentials(scheme="Bearer", credentials=token), db)


def get_configured_api_key():
    expected_key = os.getenv("ERP_API_KEY")
    if expected_key:
        return expected_key
    if os.getenv("ENVIRONMENT", "development").lower() in {"production", "prod"}:
        raise HTTPException(status_code=503, detail="API authentication is not configured")
    return None
