"""Add module permissions, Admin Power audit logs, and organization settings."""

from alembic import op
import sqlalchemy as sa


revision = "0006_admin_power"
down_revision = "0005_usernames"
branch_labels = None
depends_on = None


def upgrade():
    op.add_column(
        "organization_memberships",
        sa.Column("module_permissions", sa.JSON(), nullable=True),
    )
    op.create_table(
        "organization_audit_logs",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("actor_user_id", sa.String(), nullable=False),
        sa.Column("action", sa.String(length=100), nullable=False),
        sa.Column("target_user_id", sa.String(), nullable=True),
        sa.Column("details", sa.JSON(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_organization_audit_logs_org_id",
        "organization_audit_logs",
        ["org_id"],
    )
    op.create_table(
        "organization_settings",
        sa.Column("id", sa.String(), nullable=False),
        sa.Column("org_id", sa.String(), nullable=False),
        sa.Column("setting_key", sa.String(length=100), nullable=False),
        sa.Column("setting_value", sa.JSON(), nullable=False),
        sa.Column("updated_by", sa.String(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["org_id"], ["organizations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["updated_by"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("org_id", "setting_key", name="uq_org_setting_key"),
    )
    op.create_index(
        "ix_organization_settings_org_id",
        "organization_settings",
        ["org_id"],
    )


def downgrade():
    op.drop_index("ix_organization_settings_org_id", table_name="organization_settings")
    op.drop_table("organization_settings")
    op.drop_index("ix_organization_audit_logs_org_id", table_name="organization_audit_logs")
    op.drop_table("organization_audit_logs")
    op.drop_column("organization_memberships", "module_permissions")
