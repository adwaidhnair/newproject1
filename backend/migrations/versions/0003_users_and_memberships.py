"""Add application users and tenant memberships.

Revision ID: 0003_users_memberships
Revises: 0002_tenant_unique_keys
"""
from alembic import op
import sqlalchemy as sa

revision = "0003_users_memberships"
down_revision = "0002_tenant_unique_keys"
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        "users",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("full_name", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=True)
    op.create_table(
        "organization_memberships",
        sa.Column("id", sa.String(length=36), primary_key=True),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("org_id", sa.String(length=36), sa.ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("role", sa.String(length=32), nullable=False, server_default="viewer"),
        sa.UniqueConstraint("user_id", "org_id", name="uq_membership_user_org"),
    )
    op.create_index("ix_organization_memberships_user_id", "organization_memberships", ["user_id"])
    op.create_index("ix_organization_memberships_org_id", "organization_memberships", ["org_id"])


def downgrade():
    op.drop_index("ix_organization_memberships_org_id", table_name="organization_memberships")
    op.drop_index("ix_organization_memberships_user_id", table_name="organization_memberships")
    op.drop_table("organization_memberships")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")
