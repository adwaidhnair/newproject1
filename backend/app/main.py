import json
import hashlib
import hmac
import os
import re
import secrets
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy import case, delete, func, text, update
from sqlalchemy.dialects.postgresql import insert as postgres_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.connectors.csv_connector import CSVConnector
from app.core.database import Base, engine, get_db
from app.core.auth import (
    ACCESS_TOKEN_TTL_SECONDS,
    LOGIN_MAX_ATTEMPTS,
    LOGIN_WINDOW_SECONDS,
    SESSION_COOKIE_NAME,
    get_current_user,
    hash_password,
    issue_access_token,
    password_needs_rehash,
    require_org_access,
    validate_token_secret,
    verify_password,
)
from app.models.auth_models import (
    AuthLoginAttempt,
    BootstrapClaim,
    OrganizationAuditLog,
    OrganizationInvitation,
    OrganizationMembership,
    OrganizationSetting,
    User,
)
from app.engines.intelligence_engine import build_intelligence
from app.engines.kpi_engine import compute_kpis
from app.engines.process_mining_engine import analyze_process, simulate_improvements
from app.engines.rules_engine import evaluate_rules
from app.models.erp_models import (
    AutomationWorkflow,
    BusinessRule,
    DataImport,
    Department,
    InventorySnapshot,
    Invoice,
    Location,
    OperationalException,
    Organization,
    PurchaseOrder,
)

@asynccontextmanager
async def lifespan(_app):
    validate_token_secret()
    if os.getenv("ENVIRONMENT", "development").lower() in {"production", "prod"}:
        if not cors_origins or any(
            origin == "*" or not origin.startswith("https://") for origin in cors_origins
        ):
            raise RuntimeError("Production CORS_ORIGINS must contain only explicit HTTPS origins")
    if os.getenv("AUTO_CREATE_TABLES", "true").lower() in {"1", "true", "yes"}:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Enterprise ERP Operations Intelligence Platform",
    version="1.0.0",
    docs_url=None if os.getenv("ENVIRONMENT", "development").lower() in {"production", "prod"} else "/docs",
    redoc_url=None if os.getenv("ENVIRONMENT", "development").lower() in {"production", "prod"} else "/redoc",
    lifespan=lifespan,
)
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
csv_connector = CSVConnector()

MODULE_IDS = (
    "control",
    "risk",
    "process",
    "workflow",
    "exceptions",
    "procurement",
    "inventory",
    "rules",
    "imports",
)
MODULE_ID_SET = frozenset(MODULE_IDS)
SYSTEM_SETTING_KEYS = {
    "workspace_name": (1, 100),
    "default_currency": (3, 3),
    "timezone": (1, 64),
}


@app.get("/healthz", include_in_schema=False)
def healthz(db: Session = Depends(get_db)):
    try:
        db.execute(text("SELECT 1"))
    except SQLAlchemyError as exc:
        raise HTTPException(status_code=503, detail="Database is unavailable") from exc
    return {"status": "ok"}


@app.middleware("http")
async def authenticate_api_requests(request, call_next):
    if request.url.path.startswith("/api/v1/"):
        public_auth_route = request.url.path in {
            "/api/v1/auth/register",
            "/api/v1/auth/login",
            "/api/v1/auth/bootstrap-status",
            "/api/v1/auth/accept-invitation",
        }
        public_invite_read = request.method == "GET" and request.url.path.startswith(
            "/api/v1/auth/invitations/"
        )
        unsafe_method = request.method not in {"GET", "HEAD", "OPTIONS"}
        origin = request.headers.get("origin")
        if (
            request.cookies.get(SESSION_COOKIE_NAME)
            and unsafe_method
            and (not origin or origin not in cors_origins)
        ):
            return JSONResponse(
                status_code=403,
                content={"detail": "A trusted Origin is required for cookie-authenticated requests"},
            )
        if (
            not public_auth_route
            and not public_invite_read
            and not request.cookies.get(SESSION_COOKIE_NAME)
            and not request.headers.get("authorization", "").lower().startswith("bearer ")
        ):
            return JSONResponse(status_code=401, content={"detail": "Sign in is required"})
    return await call_next(request)


@app.middleware("http")
async def limit_request_body_size(request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 10 * 1024 * 1024:
                return JSONResponse(status_code=413, content={"detail": "Request body exceeds 10 MiB"})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})
    if request.url.path.startswith(("/api/v1/connectors/csv/", "/api/v1/connectors/files/")) and not content_length:
        return JSONResponse(
            status_code=411,
            content={"detail": "Content-Length is required for CSV uploads"},
        )
    return await call_next(request)


class RuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    module: Optional[str] = None
    metric: Optional[str] = None
    operator: Optional[str] = None
    threshold_value: Optional[float] = None
    severity: Optional[str] = None
    is_active: Optional[bool] = None


class ExceptionUpdate(BaseModel):
    status: str = Field(min_length=1)


class SimulationRequest(BaseModel):
    approval_target_days: float = 3
    delivery_sla_days: int = 0


class RegisterRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    username: str = Field(min_length=3, max_length=64, pattern="^[A-Za-z0-9][A-Za-z0-9._-]*$")
    password: str = Field(min_length=12, max_length=256)
    full_name: str = Field(min_length=1, max_length=255)
    organization_id: Optional[str] = None
    organization_name: Optional[str] = Field(default=None, max_length=255)
    industry_type: Optional[str] = Field(default=None, max_length=100)
    setup_token: str = Field(min_length=32, max_length=512)


class LoginRequest(BaseModel):
    username: str = Field(min_length=3, max_length=320)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=12, max_length=256)


class OrganizationRequest(BaseModel):
    name: str = Field(min_length=1, max_length=255)
    industry_type: str = Field(min_length=1, max_length=100)
    base_currency: str = Field(default="INR", min_length=3, max_length=3)


class MembershipRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(pattern="^(viewer|analyst|admin|owner)$")


class AdminUserCreateRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    username: str = Field(min_length=3, max_length=64, pattern="^[A-Za-z0-9][A-Za-z0-9._-]*$")
    full_name: str = Field(min_length=1, max_length=255)
    role: str = Field(default="viewer", pattern="^(viewer|analyst|admin)$")
    password: str = Field(min_length=12, max_length=256)
    module_permissions: list[str] = Field(default_factory=list)


class MemberAccessUpdate(BaseModel):
    role: Optional[str] = Field(default=None, pattern="^(viewer|analyst|admin)$")
    module_permissions: Optional[list[str]] = None
    is_active: Optional[bool] = None


class OrganizationSettingsUpdate(BaseModel):
    settings: dict[str, str]


class InvitationRequest(BaseModel):
    email: str = Field(min_length=3, max_length=320)
    role: str = Field(pattern="^(viewer|analyst|admin)$")


class InvitationAcceptRequest(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    full_name: Optional[str] = Field(default=None, min_length=1, max_length=255)
    username: Optional[str] = Field(
        default=None,
        min_length=3,
        max_length=64,
        pattern="^[A-Za-z0-9][A-Za-z0-9._-]*$",
    )
    password: str = Field(min_length=1, max_length=256)


def _normalize_email(email: str) -> str:
    normalized = email.strip().casefold()
    if "@" not in normalized or any(char.isspace() for char in normalized):
        raise HTTPException(status_code=422, detail="A valid email address is required")
    return normalized


def _normalize_username(username: str) -> str:
    normalized = username.strip().casefold()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", normalized):
        raise HTTPException(
            status_code=422,
            detail="Username must be 3–64 characters and use letters, numbers, dots, underscores, or hyphens",
        )
    return normalized


def _normalize_login_identifier(identifier: str) -> tuple[str, bool]:
    normalized = identifier.strip().casefold()
    if "@" in normalized:
        return _normalize_email(normalized), True
    return _normalize_username(normalized), False


def _set_session_cookie(response: Response, user: User) -> None:
    secure = os.getenv("ENVIRONMENT", "development").lower() in {"production", "prod"}
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=issue_access_token(user.id, user.auth_version),
        max_age=ACCESS_TOKEN_TTL_SECONDS,
        httponly=True,
        secure=secure,
        samesite="lax",
        path="/",
    )


def _login_attempt_key(email: str, request: Request) -> str:
    client_ip = request.client.host if request.client else "unknown"
    return hashlib.sha256(f"{client_ip}\0{email}".encode()).hexdigest()


def _record_login_attempt(db: Session, key: str) -> int:
    now = int(time.time())
    insert_fn = sqlite_insert if db.bind.dialect.name == "sqlite" else postgres_insert
    reset_window = AuthLoginAttempt.window_start <= now - LOGIN_WINDOW_SECONDS
    statement = insert_fn(AuthLoginAttempt).values(key=key, window_start=now, attempts=1)
    statement = statement.on_conflict_do_update(
        index_elements=[AuthLoginAttempt.key],
        set_={
            "window_start": case(
                (reset_window, now), else_=AuthLoginAttempt.window_start
            ),
            "attempts": case(
                (reset_window, 1), else_=AuthLoginAttempt.attempts + 1
            ),
        },
    )
    db.execute(statement)
    db.flush()
    return db.get(AuthLoginAttempt, key).attempts


def _bootstrap_available(db: Session) -> bool:
    claim = db.get(BootstrapClaim, 1)
    return (
        bool(os.getenv("BOOTSTRAP_SETUP_TOKEN"))
        and db.query(User.id).first() is None
        and (claim is None or claim.owner_user_id is None)
    )


def _not_found_or_tenant(db, model, record_id, org_id):
    record = db.query(model).filter(model.id == record_id, model.org_id == org_id).one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found for this organization")
    return record


def _validate_location(db, org_id, location_id):
    if location_id and not db.query(Location.id).filter(
        Location.id == location_id, Location.org_id == org_id
    ).first():
        raise HTTPException(status_code=404, detail="Location not found for this organization")


def _authorize_org(db: Session, user: User, org_id: str, minimum_role: str = "viewer"):
    role = require_org_access(db, user, org_id, minimum_role)
    return role


def _normalize_module_permissions(value: list[str]) -> list[str]:
    if not isinstance(value, list) or any(
        not isinstance(module, str) or module not in MODULE_ID_SET for module in value
    ):
        raise HTTPException(status_code=422, detail="One or more module permissions are invalid")
    return list(dict.fromkeys(value))


def _record_admin_action(
    db: Session,
    org_id: str,
    actor_user_id: str,
    action: str,
    target_user_id: Optional[str] = None,
    details: Optional[dict] = None,
) -> None:
    db.add(
        OrganizationAuditLog(
            org_id=org_id,
            actor_user_id=actor_user_id,
            action=action,
            target_user_id=target_user_id,
            details=details or {},
        )
    )


def _authorize_module(db: Session, user: User, org_id: str, module: str) -> str:
    role = _authorize_org(db, user, org_id)
    if role in {"owner", "admin"}:
        return role
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.org_id == org_id,
        OrganizationMembership.user_id == user.id,
    ).one()
    # A NULL permission list predates module-level RBAC. Preserve those existing
    # members' access while newly managed accounts use their explicit checklist.
    allowed_modules = MODULE_IDS if membership.module_permissions is None else membership.module_permissions
    if module not in allowed_modules:
        raise HTTPException(status_code=403, detail="This module is not enabled for your account")
    return role


@app.get("/api/v1/auth/bootstrap-status")
def auth_bootstrap_status(db: Session = Depends(get_db)):
    return {"registration_enabled": _bootstrap_available(db)}


@app.post("/api/v1/auth/register")
def register(request: RegisterRequest, response: Response, db: Session = Depends(get_db)):
    setup_token = os.getenv("BOOTSTRAP_SETUP_TOKEN", "")
    if not setup_token or not hmac.compare_digest(request.setup_token, setup_token):
        raise HTTPException(status_code=403, detail="Invalid first-owner setup token")
    if not _bootstrap_available(db):
        raise HTTPException(status_code=403, detail="First-owner setup is closed")

    email = _normalize_email(request.email)
    username = _normalize_username(request.username)
    full_name = request.full_name.strip()
    if not full_name:
        raise HTTPException(status_code=422, detail="Full name is required")

    try:
        insert_fn = sqlite_insert if db.bind.dialect.name == "sqlite" else postgres_insert
        db.execute(
            insert_fn(BootstrapClaim)
            .values(id=1, owner_user_id=None)
            .on_conflict_do_nothing(index_elements=[BootstrapClaim.id])
        )
        organization = (
            db.query(Organization)
            .filter(Organization.id == request.organization_id)
            .one_or_none()
            if request.organization_id
            else None
        )
        if request.organization_id and organization is None:
            raise HTTPException(status_code=404, detail="Organization not found")
        if organization is None:
            if not request.organization_name or not request.industry_type:
                raise HTTPException(
                    status_code=422,
                    detail="Choose an organization or provide a name and industry",
                )
            organization = Organization(
                name=request.organization_name.strip(),
                industry_type=request.industry_type.strip().upper(),
                base_currency="INR",
            )
            db.add(organization)
            db.flush()

        user = User(
            id=str(uuid.uuid4()),
            email=email,
            username=username,
            password_hash=hash_password(request.password),
            full_name=full_name,
            is_active=True,
        )
        db.add(user)
        db.flush()
        db.add(OrganizationMembership(
            id=str(uuid.uuid4()), user_id=user.id, org_id=organization.id, role="owner"
        ))
        claim_updated = (
            db.query(BootstrapClaim)
            .filter(BootstrapClaim.id == 1, BootstrapClaim.owner_user_id.is_(None))
            .update({"owner_user_id": user.id}, synchronize_session=False)
        )
        if claim_updated != 1:
            raise HTTPException(status_code=409, detail="First-owner setup has already been claimed")
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="An account with this username or email already exists")
    except Exception:
        db.rollback()
        raise
    _set_session_cookie(response, user)
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
        }
    }


@app.post("/api/v1/auth/login")
def login(request: LoginRequest, http_request: Request, response: Response, db: Session = Depends(get_db)):
    identifier, is_email = _normalize_login_identifier(request.username)
    attempt_key = _login_attempt_key(identifier, http_request)
    try:
        attempts = _record_login_attempt(db, attempt_key)
        db.commit()
    except Exception:
        db.rollback()
        raise
    if attempts > LOGIN_MAX_ATTEMPTS:
        raise HTTPException(status_code=429, detail="Too many sign-in attempts; try again later")

    user_query = db.query(User)
    user = user_query.filter(
        func.lower(User.email if is_email else User.username) == identifier
    ).one_or_none()
    valid_password = verify_password(
        request.password,
        user.password_hash if user is not None else hash_password("not-a-real-password"),
    )
    if user is None or not user.is_active or not valid_password:
        raise HTTPException(status_code=401, detail="Invalid username or password")
    if password_needs_rehash(user.password_hash):
        user.password_hash = hash_password(request.password)
    db.execute(delete(AuthLoginAttempt).where(AuthLoginAttempt.key == attempt_key))
    db.commit()
    _set_session_cookie(response, user)
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
        }
    }


@app.get("/api/v1/auth/me")
def auth_me(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    memberships = db.query(OrganizationMembership).filter(OrganizationMembership.user_id == user.id).all()
    organization_ids = [membership.org_id for membership in memberships]
    organizations_by_id = {
        org.id: org
        for org in db.query(Organization).filter(Organization.id.in_(organization_ids)).all()
    } if organization_ids else {}
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
        },
        "organizations": [
            {
                "id": m.org_id,
                "name": organizations_by_id[m.org_id].name,
                "industry_type": organizations_by_id[m.org_id].industry_type,
                "role": m.role,
                "module_permissions": (
                    list(MODULE_IDS)
                    if m.role in {"owner", "admin"} or m.module_permissions is None
                    else m.module_permissions
                ),
            }
            for m in memberships
            if m.org_id in organizations_by_id
        ],
    }


@app.post("/api/v1/auth/change-password")
def change_password(
    request: ChangePasswordRequest,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    if not verify_password(request.current_password, user.password_hash):
        raise HTTPException(status_code=401, detail="Current password is incorrect")
    if hmac.compare_digest(request.current_password, request.new_password):
        raise HTTPException(status_code=422, detail="Choose a password different from your current password")

    user.password_hash = hash_password(request.new_password)
    user.auth_version += 1
    db.commit()
    _set_session_cookie(response, user)
    return {"password_changed": True}


@app.post("/api/v1/auth/logout")
def logout(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    user.auth_version += 1
    db.commit()
    secure = os.getenv("ENVIRONMENT", "development").lower() in {"production", "prod"}
    response.delete_cookie(
        key=SESSION_COOKIE_NAME, path="/", httponly=True, secure=secure, samesite="lax"
    )
    return {"signed_out": True}


@app.post("/api/v1/organizations/{org_id}/invitations")
def create_invitation(
    org_id: str,
    request: InvitationRequest,
    http_request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    role = _authorize_org(db, user, org_id, "admin")
    if request.role == "admin" and role != "owner":
        raise HTTPException(status_code=403, detail="Only an organization owner can invite administrators")
    email = _normalize_email(request.email)
    token = secrets.token_urlsafe(32)
    invitation = OrganizationInvitation(
        id=str(uuid.uuid4()),
        org_id=org_id,
        email=email,
        role=request.role,
        token_hash=hashlib.sha256(token.encode()).hexdigest(),
        created_by=user.id,
        expires_at=int(time.time()) + 7 * 24 * 60 * 60,
    )
    db.add(invitation)
    _record_admin_action(
        db,
        org_id,
        user.id,
        "invitation.created",
        details={"email": email, "role": request.role},
    )
    db.commit()
    origin = http_request.headers.get("origin", "").rstrip("/")
    return {
        "email": invitation.email,
        "role": invitation.role,
        "expires_at": invitation.expires_at,
        "invitation_token": token,
        "invitation_url": f"{origin}/?invite={token}" if origin else None,
    }


@app.get("/api/v1/auth/invitations/{token}")
def invitation_details(token: str, db: Session = Depends(get_db)):
    token_hash = hashlib.sha256(token.encode()).hexdigest()
    invitation = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.token_hash == token_hash
    ).one_or_none()
    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.expires_at <= int(time.time())
    ):
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")
    organization = db.query(Organization).filter(Organization.id == invitation.org_id).one_or_none()
    return {
        "email": invitation.email,
        "role": invitation.role,
        "organization_name": organization.name if organization else "Organization",
    }


@app.post("/api/v1/auth/accept-invitation")
def accept_invitation(
    request: InvitationAcceptRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    invitation = db.query(OrganizationInvitation).filter(
        OrganizationInvitation.token_hash == hashlib.sha256(request.token.encode()).hexdigest()
    ).one_or_none()
    if (
        invitation is None
        or invitation.accepted_at is not None
        or invitation.expires_at <= int(time.time())
    ):
        raise HTTPException(status_code=404, detail="Invitation is invalid or expired")

    user = db.query(User).filter(User.email == invitation.email).one_or_none()
    if user is not None:
        if not user.is_active or not verify_password(request.password, user.password_hash):
            raise HTTPException(status_code=401, detail="Invalid username or password")
    else:
        if not request.full_name or not request.full_name.strip():
            raise HTTPException(status_code=422, detail="Full name is required for a new account")
        if not request.username:
            raise HTTPException(status_code=422, detail="Username is required for a new account")
        if len(request.password) < 12:
            raise HTTPException(status_code=422, detail="Password must be at least 12 characters")
        user = User(
            id=str(uuid.uuid4()),
            email=invitation.email,
            username=_normalize_username(request.username),
            password_hash=hash_password(request.password),
            full_name=request.full_name.strip(),
            is_active=True,
        )
        db.add(user)
        db.flush()

    existing = db.query(OrganizationMembership).filter(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.org_id == invitation.org_id,
    ).one_or_none()
    if existing is not None:
        raise HTTPException(status_code=409, detail="User already belongs to this organization")
    db.add(OrganizationMembership(
        id=str(uuid.uuid4()),
        user_id=user.id,
        org_id=invitation.org_id,
        role=invitation.role,
    ))
    invitation.accepted_at = int(time.time())
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Invitation has already been accepted")
    _set_session_cookie(response, user)
    return {
        "user": {
            "id": user.id,
            "email": user.email,
            "username": user.username,
            "full_name": user.full_name,
        }
    }


@app.post("/api/v1/organizations")
def create_organization(
    request: OrganizationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    is_owner = db.query(OrganizationMembership.id).filter(
        OrganizationMembership.user_id == user.id,
        OrganizationMembership.role == "owner",
    ).first()
    if not is_owner:
        raise HTTPException(status_code=403, detail="Only an organization owner can create organizations")

    try:
        organization = Organization(
            name=request.name.strip(),
            industry_type=request.industry_type.strip().upper(),
            base_currency=request.base_currency.upper(),
        )
        db.add(organization)
        db.flush()
        db.add(OrganizationMembership(
            id=str(uuid.uuid4()), user_id=user.id, org_id=organization.id, role="owner"
        ))
        _record_admin_action(
            db,
            organization.id,
            user.id,
            "organization.created",
            details={"name": organization.name, "industry_type": organization.industry_type},
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    db.refresh(organization)
    return organization


@app.post("/api/v1/organizations/{org_id}/members")
def add_org_member(
    org_id: str,
    request: MembershipRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actor_role = _authorize_org(db, user, org_id, "admin")
    if request.role == "owner":
        _authorize_org(db, user, org_id, "owner")
    if request.role == "admin" and actor_role != "owner":
        raise HTTPException(status_code=403, detail="Only an organization owner can grant administrator access")
    target = db.query(User).filter(User.email == _normalize_email(request.email), User.is_active.is_(True)).one_or_none()
    if target is None:
        raise HTTPException(status_code=404, detail="User not found")
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.org_id == org_id, OrganizationMembership.user_id == target.id
    ).one_or_none()
    if membership:
        membership.role = request.role
    else:
        membership = OrganizationMembership(id=str(uuid.uuid4()), user_id=target.id, org_id=org_id, role=request.role)
        db.add(membership)
    _record_admin_action(
        db,
        org_id,
        user.id,
        "user.role_updated",
        target.id,
        {"role": request.role},
    )
    db.commit()
    return {"user_id": target.id, "org_id": org_id, "role": request.role}


@app.get("/api/v1/organizations/{org_id}/members")
def list_org_members(
    org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _authorize_org(db, user, org_id, "admin")
    members = (
        db.query(User, OrganizationMembership)
        .join(OrganizationMembership, OrganizationMembership.user_id == User.id)
        .filter(OrganizationMembership.org_id == org_id)
        .order_by(User.email)
        .all()
    )
    return [
        {
            "user_id": member.id,
            "email": member.email,
            "username": member.username,
            "full_name": member.full_name,
            "role": membership.role,
            "is_active": member.is_active,
            "module_permissions": (
                list(MODULE_IDS)
                if membership.role in {"owner", "admin"} or membership.module_permissions is None
                else membership.module_permissions
            ),
        }
        for member, membership in members
    ]


@app.post("/api/v1/organizations/{org_id}/users", status_code=201)
def create_managed_user(
    org_id: str,
    request: AdminUserCreateRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actor_role = _authorize_org(db, user, org_id, "admin")
    if request.role == "admin" and actor_role != "owner":
        raise HTTPException(status_code=403, detail="Only an organization owner can create administrators")
    email = _normalize_email(request.email)
    username = _normalize_username(request.username)
    full_name = request.full_name.strip()
    if not full_name:
        raise HTTPException(status_code=422, detail="Name is required")
    permissions = _normalize_module_permissions(request.module_permissions)
    if db.query(User.id).filter((User.email == email) | (User.username == username)).first():
        raise HTTPException(status_code=409, detail="That email or username is already in use")

    new_user = User(
        id=str(uuid.uuid4()),
        email=email,
        username=username,
        full_name=full_name,
        password_hash=hash_password(request.password),
    )
    membership = OrganizationMembership(
        id=str(uuid.uuid4()),
        user_id=new_user.id,
        org_id=org_id,
        role=request.role,
        module_permissions=permissions,
    )
    db.add_all([new_user, membership])
    _record_admin_action(
        db,
        org_id,
        user.id,
        "user.created",
        new_user.id,
        {"role": request.role, "module_permissions": permissions},
    )
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise HTTPException(status_code=409, detail="That email or username is already in use") from exc
    return {
        "user_id": new_user.id,
        "email": new_user.email,
        "username": new_user.username,
        "full_name": new_user.full_name,
        "role": membership.role,
        "module_permissions": membership.module_permissions,
    }


@app.patch("/api/v1/organizations/{org_id}/members/{member_user_id}")
def update_member_access(
    org_id: str,
    member_user_id: str,
    request: MemberAccessUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    actor_role = _authorize_org(db, user, org_id, "admin")
    target = db.query(User).filter(User.id == member_user_id).one_or_none()
    membership = db.query(OrganizationMembership).filter(
        OrganizationMembership.org_id == org_id,
        OrganizationMembership.user_id == member_user_id,
    ).one_or_none()
    if target is None or membership is None:
        raise HTTPException(status_code=404, detail="Organization member not found")
    if membership.role == "owner":
        raise HTTPException(status_code=403, detail="The organization owner cannot be managed here")
    if membership.role == "admin" and actor_role != "owner":
        raise HTTPException(status_code=403, detail="Only the organization owner can manage administrators")
    changes = request.model_dump(exclude_unset=True)
    if not changes:
        raise HTTPException(status_code=422, detail="At least one access change is required")
    if changes.get("is_active") is False and target.id == user.id:
        raise HTTPException(status_code=422, detail="You cannot deactivate your own account")
    if changes.get("role") == "admin" and actor_role != "owner":
        raise HTTPException(status_code=403, detail="Only the organization owner can grant administrator access")
    previous = {
        "role": membership.role,
        "module_permissions": membership.module_permissions,
        "is_active": target.is_active,
    }
    if "role" in changes:
        membership.role = changes["role"]
    if "module_permissions" in changes:
        membership.module_permissions = _normalize_module_permissions(changes["module_permissions"])
    if "is_active" in changes:
        target.is_active = changes["is_active"]
    if membership.role in {"owner", "admin"}:
        membership.module_permissions = list(MODULE_IDS)
    updated = {
        "role": membership.role,
        "module_permissions": membership.module_permissions,
        "is_active": target.is_active,
    }
    _record_admin_action(
        db,
        org_id,
        user.id,
        "user.access_updated",
        target.id,
        {"before": previous, "after": updated},
    )
    db.commit()
    return {
        "user_id": target.id,
        "email": target.email,
        "username": target.username,
        "full_name": target.full_name,
        **updated,
    }


@app.get("/api/v1/organizations/{org_id}/admin-power/settings")
def admin_power_settings(
    org_id: str,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_org(db, user, org_id, "admin")
    org = db.query(Organization).filter(Organization.id == org_id).one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    stored = {
        setting.setting_key: setting.setting_value
        for setting in db.query(OrganizationSetting).filter(OrganizationSetting.org_id == org_id).all()
    }
    return {
        "settings": {
            "workspace_name": org.name,
            "default_currency": org.base_currency,
            "timezone": stored.get("timezone", "Asia/Kolkata"),
        }
    }


@app.put("/api/v1/organizations/{org_id}/admin-power/settings")
def update_admin_power_settings(
    org_id: str,
    request: OrganizationSettingsUpdate,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_org(db, user, org_id, "admin")
    org = db.query(Organization).filter(Organization.id == org_id).one_or_none()
    if org is None:
        raise HTTPException(status_code=404, detail="Organization not found")
    if not request.settings or set(request.settings) - SYSTEM_SETTING_KEYS.keys():
        raise HTTPException(status_code=422, detail="One or more system settings are not supported")
    for key, value in request.settings.items():
        min_length, max_length = SYSTEM_SETTING_KEYS[key]
        normalized = value.strip()
        if not min_length <= len(normalized) <= max_length:
            raise HTTPException(status_code=422, detail=f"Invalid value for {key}")
        if key == "workspace_name":
            org.name = normalized
        elif key == "default_currency":
            if not normalized.isalpha():
                raise HTTPException(status_code=422, detail="Currency must use three letters")
            org.base_currency = normalized.upper()
        else:
            setting = db.query(OrganizationSetting).filter(
                OrganizationSetting.org_id == org_id,
                OrganizationSetting.setting_key == key,
            ).one_or_none()
            if setting is None:
                setting = OrganizationSetting(
                    org_id=org_id,
                    setting_key=key,
                    setting_value=normalized,
                    updated_by=user.id,
                )
                db.add(setting)
            else:
                setting.setting_value = normalized
                setting.updated_by = user.id
    _record_admin_action(
        db,
        org_id,
        user.id,
        "settings.updated",
        details={"keys": sorted(request.settings)},
    )
    db.commit()
    return admin_power_settings(org_id, user, db)


@app.get("/api/v1/organizations/{org_id}/admin-power/audit-logs")
def admin_power_audit_logs(
    org_id: str,
    limit: int = 100,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_org(db, user, org_id, "admin")
    limit = max(1, min(limit, 200))
    logs = (
        db.query(OrganizationAuditLog, User.full_name, User.username)
        .join(User, User.id == OrganizationAuditLog.actor_user_id)
        .filter(OrganizationAuditLog.org_id == org_id)
        .order_by(OrganizationAuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": log.id,
            "actor": actor_name,
            "actor_username": actor_username,
            "action": log.action,
            "target_user_id": log.target_user_id,
            "details": log.details,
            "created_at": log.created_at,
        }
        for log, actor_name, actor_username in logs
    ]


@app.get("/api/v1/bootstrap")
def bootstrap(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    memberships = db.query(OrganizationMembership).filter(OrganizationMembership.user_id == user.id).all()
    org_ids = [membership.org_id for membership in memberships]
    organizations = db.query(Organization).filter(Organization.id.in_(org_ids)).all() if org_ids else []
    return {
        "organizations": [
            {
                "id": org.id,
                "name": org.name,
                "industry_type": org.industry_type,
                "base_currency": org.base_currency,
            }
            for org in organizations
        ],
        "seeded": bool(organizations),
    }


@app.get("/api/v1/organizations")
def organizations(user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    org_ids = [m.org_id for m in db.query(OrganizationMembership).filter(OrganizationMembership.user_id == user.id).all()]
    return db.query(Organization).filter(Organization.id.in_(org_ids)).all()


@app.get("/api/v1/tenant-context/{org_id}")
def tenant_context(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _authorize_org(db, user, org_id)
    org = db.query(Organization).filter(Organization.id == org_id).one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {
        "organization": org,
        "locations": db.query(Location).filter(Location.org_id == org_id).all(),
        "departments": db.query(Department).filter(Department.org_id == org_id).all(),
    }


@app.get("/api/v1/organization/{org_id}/industry")
def organization_industry(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _authorize_org(db, user, org_id)
    org = db.query(Organization).filter(Organization.id == org_id).one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"industry_type": org.industry_type, "industry_config": org.industry_config or {}}


@app.get("/api/v1/control-tower/{org_id}")
def control_tower(org_id: str, location_id: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _authorize_module(db, user, org_id, "control")
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    _validate_location(db, org_id, location_id)
    return compute_kpis(db, org_id, location_id)


@app.get("/api/v1/intelligence/{org_id}")
def intelligence(org_id: str, location_id: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _authorize_module(db, user, org_id, "risk")
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    _validate_location(db, org_id, location_id)
    return build_intelligence(db, org_id, location_id)


@app.get("/api/v1/process-mining/{org_id}")
def process_mining(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _authorize_module(db, user, org_id, "process")
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    return analyze_process(db, org_id)


@app.post("/api/v1/simulate/{org_id}")
def simulate(org_id: str, request: SimulationRequest, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _authorize_module(db, user, org_id, "process")
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    return simulate_improvements(
        db, org_id, request.approval_target_days, request.delivery_sla_days
    )


@app.get("/api/v1/rules/{org_id}")
def rules(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _authorize_module(db, user, org_id, "rules")
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    return db.query(BusinessRule).filter(BusinessRule.org_id == org_id).all()


@app.patch("/api/v1/rules/{rule_id}")
def update_rule(
    rule_id: str, update: RuleUpdate, org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _authorize_module(db, user, org_id, "rules")
    _authorize_org(db, user, org_id, "admin")
    rule = _not_found_or_tenant(db, BusinessRule, rule_id, org_id)
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    evaluate_rules(db, rule.org_id)
    db.commit()
    return rule


@app.post("/api/v1/rules/{org_id}/evaluate")
def reevaluate_rules(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _authorize_module(db, user, org_id, "rules")
    _authorize_org(db, user, org_id, "analyst")
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"exceptions_generated": len(evaluate_rules(db, org_id))}


@app.get("/api/v1/workflows/{org_id}")
def workflows(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _authorize_module(db, user, org_id, "workflow")
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    return (
        db.query(AutomationWorkflow)
        .filter(AutomationWorkflow.org_id == org_id)
        .order_by(AutomationWorkflow.created_at.desc())
        .all()
    )


@app.post("/api/v1/workflows/{org_id}")
def create_workflow(org_id: str, workflow: dict, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _authorize_module(db, user, org_id, "workflow")
    _authorize_org(db, user, org_id, "admin")
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    allowed = {
        "workflow_name",
        "trigger_module",
        "trigger_severity",
        "action_type",
        "action_target",
        "is_active",
    }
    if not all(workflow.get(field) for field in allowed - {"is_active"}):
        raise HTTPException(status_code=422, detail="Workflow requires trigger and action fields")
    record = AutomationWorkflow(org_id=org_id, **{key: value for key, value in workflow.items() if key in allowed})
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.get("/api/v1/exceptions/{org_id}/list")
def list_exceptions(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _authorize_module(db, user, org_id, "exceptions")
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    return (
        db.query(OperationalException)
        .filter(OperationalException.org_id == org_id)
        .order_by(OperationalException.status, OperationalException.severity)
        .all()
    )


@app.patch("/api/v1/exceptions/{exc_id}")
def update_exception(
    exc_id: str, update: ExceptionUpdate, org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _authorize_module(db, user, org_id, "exceptions")
    _authorize_org(db, user, org_id, "analyst")
    exc = _not_found_or_tenant(db, OperationalException, exc_id, org_id)
    status = update.status.upper()
    if status not in {"OPEN", "IN_PROGRESS", "RESOLVED", "DISMISSED"}:
        raise HTTPException(status_code=422, detail="Unsupported exception status")
    exc.status = status
    exc.resolved_by = user.full_name if status in {"RESOLVED", "DISMISSED"} else None
    db.commit()
    return exc


@app.get("/api/v1/imports/{org_id}")
def imports(org_id: str, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _authorize_module(db, user, org_id, "imports")
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    return (
        db.query(DataImport)
        .filter(DataImport.org_id == org_id)
        .order_by(DataImport.created_at.desc())
        .all()
    )


@app.get("/api/v1/procurement/{org_id}")
def procurement(org_id: str, location_id: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    _authorize_module(db, user, org_id, "procurement")
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    _validate_location(db, org_id, location_id)
    query = db.query(PurchaseOrder).filter(PurchaseOrder.org_id == org_id)
    if location_id:
        query = query.filter(PurchaseOrder.location_id == location_id)
    return query.order_by(PurchaseOrder.order_date.desc()).all()


@app.get("/api/v1/inventory-invoices/{org_id}")
def inventory_invoices(
    org_id: str, location_id: Optional[str] = None, user: User = Depends(get_current_user), db: Session = Depends(get_db)
):
    _authorize_module(db, user, org_id, "inventory")
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    _validate_location(db, org_id, location_id)
    inventory_query = db.query(InventorySnapshot).filter(InventorySnapshot.org_id == org_id)
    invoice_query = db.query(Invoice).filter(Invoice.org_id == org_id)
    if location_id:
        inventory_query = inventory_query.filter(InventorySnapshot.location_id == location_id)
        invoice_query = invoice_query.filter(Invoice.location_id == location_id)
    return {
        "inventory": inventory_query.all(),
        "invoices": invoice_query.all(),
    }


async def _upload_payload(file: UploadFile, mapping: Optional[str] = None):
    file_name = Path((file.filename or "upload.csv").replace("\\", "/")).name
    if Path(file_name).suffix.casefold() not in {".csv", ".xlsx"}:
        raise HTTPException(status_code=415, detail="Upload a CSV or Excel .xlsx file")
    parsed_mapping = None
    if mapping is not None:
        try:
            parsed_mapping = json.loads(mapping)
        except json.JSONDecodeError as exc:
            raise HTTPException(status_code=422, detail="mapping must be a JSON object") from exc
        if not isinstance(parsed_mapping, dict) or not all(
            isinstance(key, str) and isinstance(value, str)
            for key, value in parsed_mapping.items()
        ):
            raise HTTPException(status_code=422, detail="mapping must map source columns to canonical fields")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="File exceeds the 10 MiB upload limit")
    return content, parsed_mapping, file_name


@app.post("/api/v1/connectors/files/suggest-mapping")
async def suggest_file_mapping(
    org_id: str = Form(...),
    file: UploadFile = File(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_module(db, user, org_id, "imports")
    try:
        content, _, file_name = await _upload_payload(file)
        return csv_connector.suggest_mapping(content, file_name)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/connectors/csv/preview")
async def csv_preview(
    org_id: str = Form(...),
    file: UploadFile = File(...),
    mapping: str = Form(...),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_module(db, user, org_id, "imports")
    try:
        content, parsed_mapping, file_name = await _upload_payload(file, mapping)
        return csv_connector.preview(content, parsed_mapping, file_name, db=db, org_id=org_id)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/connectors/csv/ingest/{org_id}")
async def csv_ingest(
    org_id: str,
    file: UploadFile = File(...),
    mapping: str = Form(...),
    imported_by: Optional[str] = Form(None),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    _authorize_module(db, user, org_id, "imports")
    _authorize_org(db, user, org_id, "analyst")
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    try:
        content, parsed_mapping, file_name = await _upload_payload(file, mapping)
        return csv_connector.ingest(
            db,
            org_id,
            content,
            file_name,
            parsed_mapping,
            imported_by,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
