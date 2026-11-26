import os
import secrets
from typing import Optional

from fastapi import Header, HTTPException


def require_api_key(
    authorization: Optional[str] = Header(default=None),
    x_api_key: Optional[str] = Header(default=None),
):
    expected_key = get_configured_api_key()
    if expected_key is None:
        return

    supplied_key = x_api_key
    if authorization and authorization.lower().startswith("bearer "):
        supplied_key = authorization[7:].strip()
    if supplied_key is None or not secrets.compare_digest(supplied_key, expected_key):
        raise HTTPException(status_code=401, detail="Invalid or missing API key")


def get_configured_api_key():
    expected_key = os.getenv("ERP_API_KEY")
    if expected_key:
        return expected_key
    if os.getenv("ENVIRONMENT", "development").lower() in {"production", "prod"}:
        raise HTTPException(status_code=503, detail="API authentication is not configured")
    return None
