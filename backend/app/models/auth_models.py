import uuid

from sqlalchemy import Boolean, Column, DateTime, ForeignKey, Integer, JSON, String, UniqueConstraint, func

from app.core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True)
    email = Column(String, nullable=False, unique=True, index=True)
    username = Column(String(320), nullable=False, unique=True, index=True)
    password_hash = Column(String, nullable=False)
    full_name = Column(String, nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    auth_version = Column(Integer, nullable=False, default=0, server_default="0")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OrganizationMembership(Base):
    __tablename__ = "organization_memberships"
    __table_args__ = (UniqueConstraint("user_id", "org_id", name="uq_membership_user_org"),)

    id = Column(String, primary_key=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    org_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    role = Column(String, nullable=False, default="viewer")
    module_permissions = Column(JSON, nullable=True)


class BootstrapClaim(Base):
    __tablename__ = "auth_bootstrap_claims"

    id = Column(Integer, primary_key=True)
    owner_user_id = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=True, unique=True)


class OrganizationInvitation(Base):
    __tablename__ = "organization_invitations"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    email = Column(String(320), nullable=False, index=True)
    role = Column(String(20), nullable=False)
    token_hash = Column(String(64), nullable=False, unique=True, index=True)
    created_by = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    expires_at = Column(Integer, nullable=False)
    accepted_at = Column(Integer, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AuthLoginAttempt(Base):
    __tablename__ = "auth_login_attempts"

    key = Column(String(64), primary_key=True)
    window_start = Column(Integer, nullable=False)
    attempts = Column(Integer, nullable=False)


class OrganizationAuditLog(Base):
    __tablename__ = "organization_audit_logs"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    actor_user_id = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    action = Column(String(100), nullable=False)
    target_user_id = Column(String, ForeignKey("users.id", ondelete="SET NULL"), nullable=True)
    details = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())


class OrganizationSetting(Base):
    __tablename__ = "organization_settings"
    __table_args__ = (UniqueConstraint("org_id", "setting_key", name="uq_org_setting_key"),)

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    org_id = Column(String, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True)
    setting_key = Column(String(100), nullable=False)
    setting_value = Column(JSON, nullable=False)
    updated_by = Column(String, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    updated_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
