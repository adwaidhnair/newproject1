"""Make PO and invoice identifiers unique within an organization.

Revision ID: 0002_tenant_unique_keys
Revises: 0001_initial_schema
"""
from alembic import op
import sqlalchemy as sa

revision = "0002_tenant_unique_keys"
down_revision = "0001_initial_schema"
branch_labels = None
depends_on = None


def upgrade():
    bind = op.get_bind()
    duplicates = bind.execute(
        sa.text(
            "SELECT org_id, po_number FROM purchase_orders "
            "GROUP BY org_id, po_number HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicates:
        raise RuntimeError(
            "Cannot add tenant-scoped PO uniqueness: duplicate "
            f"({duplicates.org_id}, {duplicates.po_number}) exists; deduplicate before migrating."
        )
    duplicates = bind.execute(
        sa.text(
            "SELECT org_id, invoice_number FROM invoices "
            "GROUP BY org_id, invoice_number HAVING COUNT(*) > 1 LIMIT 1"
        )
    ).first()
    if duplicates:
        raise RuntimeError(
            "Cannot add tenant-scoped invoice uniqueness: duplicate "
            f"({duplicates.org_id}, {duplicates.invoice_number}) exists; deduplicate before migrating."
        )
    # Named unique indexes are portable across SQLite and PostgreSQL, and match
    # the model metadata used by Alembic's schema-drift checks.
    existing_purchase_order_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("purchase_orders")
    }
    if "uq_purchase_orders_org_po_number" not in existing_purchase_order_indexes:
        op.create_index(
            "uq_purchase_orders_org_po_number",
            "purchase_orders",
            ["org_id", "po_number"],
            unique=True,
        )
    existing_invoice_indexes = {
        index["name"] for index in sa.inspect(bind).get_indexes("invoices")
    }
    if "uq_invoices_org_invoice_number" not in existing_invoice_indexes:
        op.create_index(
            "uq_invoices_org_invoice_number",
            "invoices",
            ["org_id", "invoice_number"],
            unique=True,
        )


def downgrade():
    op.drop_index("uq_invoices_org_invoice_number", table_name="invoices")
    op.drop_index("uq_purchase_orders_org_po_number", table_name="purchase_orders")
