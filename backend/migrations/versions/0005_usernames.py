"""Add usernames for password-based sign-in.

Revision ID: 0005_usernames
Revises: 0004_auth_sessions
"""
from alembic import op
import sqlalchemy as sa


revision = "0005_usernames"
down_revision = "0004_auth_sessions"
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table("users") as batch_op:
        batch_op.add_column(sa.Column("username", sa.String(length=320), nullable=True))

    # Existing accounts keep their email as a backwards-compatible username.
    op.execute(sa.text("UPDATE users SET username = email"))

    with op.batch_alter_table("users") as batch_op:
        batch_op.alter_column(
            "username",
            existing_type=sa.String(length=320),
            nullable=False,
        )

    op.create_index("ix_users_username", "users", ["username"], unique=True)


def downgrade():
    op.drop_index("ix_users_username", table_name="users")
    with op.batch_alter_table("users") as batch_op:
        batch_op.drop_column("username")
