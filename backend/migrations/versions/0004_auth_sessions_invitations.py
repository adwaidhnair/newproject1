"""Add revocable sessions, atomic owner bootstrap and invitations.

Revision ID: 0004_auth_sessions
Revises: 0003_users_memberships
"""
from alembic import op
import sqlalchemy as sa

revision = "0004_auth_sessions"
down_revision = "0003_users_memberships"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "users",
        sa.Column("auth_version", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "users",
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_table(
        "auth_bootstrap_claims",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("owner_user_id", sa.String(length=36), nullable=True),
        sa.ForeignKeyConstraint(["owner_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.UniqueConstraint("owner_user_id", name="uq_auth_bootstrap_owner"),
    )
    op.bulk_insert(
        sa.table("auth_bootstrap_claims", sa.column("id", sa.Integer()), sa.column("owner_user_id", sa.String())),
        [{"id": 1, "owner_user_id": None}],
    )
    op.create_table(
        "organization_invitations",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("org_id", sa.String(length=36), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("role", sa.String(length=20), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False),
        sa.Column("created_by", sa.String(length=36), nullable=False),
        sa.Column("expires_at", sa.Integer(), nullable=False),
        sa.Column("accepted_at", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], ondelete="RESTRICT"),
    )
    op.create_index("ix_organization_invitations_org_id", "organization_invitations", ["org_id"])
    op.create_index("ix_organization_invitations_email", "organization_invitations", ["email"])
    op.create_index("ix_organization_invitations_token_hash", "organization_invitations", ["token_hash"], unique=True)
    op.create_table(
        "auth_login_attempts",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("window_start", sa.Integer(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False),
    )


def downgrade():
    op.drop_table("auth_login_attempts")
    op.drop_index("ix_organization_invitations_token_hash", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_email", table_name="organization_invitations")
    op.drop_index("ix_organization_invitations_org_id", table_name="organization_invitations")
    op.drop_table("organization_invitations")
    op.drop_table("auth_bootstrap_claims")
    op.drop_column("users", "created_at")
    op.drop_column("users", "auth_version")
