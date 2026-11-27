"""Create initial ERP schema.

Revision ID: 0001_initial_schema
Revises:
"""
from alembic import op

from app.core.database import Base
from app.models import erp_models  # noqa: F401

revision = "0001_initial_schema"
down_revision = None
branch_labels = None
depends_on = None
ERP_TABLES = [
    erp_models.Organization.__table__,
    erp_models.Location.__table__,
    erp_models.Department.__table__,
    erp_models.PurchaseOrder.__table__,
    erp_models.InventorySnapshot.__table__,
    erp_models.Invoice.__table__,
    erp_models.BusinessRule.__table__,
    erp_models.OperationalException.__table__,
    erp_models.ProcessEvent.__table__,
    erp_models.DataImport.__table__,
    erp_models.AutomationWorkflow.__table__,
]


def upgrade():
    bind = op.get_bind()
    Base.metadata.create_all(bind=bind, tables=ERP_TABLES)


def downgrade():
    bind = op.get_bind()
    Base.metadata.drop_all(bind=bind, tables=ERP_TABLES)
