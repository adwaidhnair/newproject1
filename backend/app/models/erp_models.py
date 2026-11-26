import uuid

from sqlalchemy import Boolean, Column, Date, DateTime, Float, ForeignKey, Index, Integer, JSON, String

from app.core.database import Base


def new_id():
    return str(uuid.uuid4())


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(String(36), primary_key=True, default=new_id)
    name = Column(String(255), nullable=False)
    industry_type = Column(String(100), nullable=False)
    base_currency = Column(String(3), nullable=False, default="INR")
    industry_config = Column(JSON, nullable=True)


class Location(Base):
    __tablename__ = "locations"

    id = Column(String(36), primary_key=True, default=new_id)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)
    location_type = Column(String(100), nullable=False)
    region = Column(String(100), nullable=True)


class Department(Base):
    __tablename__ = "departments"

    id = Column(String(36), primary_key=True, default=new_id)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    name = Column(String(255), nullable=False)


class PurchaseOrder(Base):
    __tablename__ = "purchase_orders"
    __table_args__ = (
        Index("uq_purchase_orders_org_po_number", "org_id", "po_number", unique=True),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    location_id = Column(String(36), ForeignKey("locations.id"), nullable=False)
    dept_id = Column(String(36), ForeignKey("departments.id"), nullable=True)
    po_number = Column(String(100), nullable=False, index=True)
    vendor_name = Column(String(255), nullable=False)
    item_code = Column(String(100), nullable=False)
    item_description = Column(String(500), nullable=False)
    quantity = Column(Float, nullable=False)
    unit_price = Column(Float, nullable=False)
    total_amount = Column(Float, nullable=False)
    order_date = Column(Date, nullable=False)
    expected_delivery_date = Column(Date, nullable=True)
    actual_delivery_date = Column(Date, nullable=True)
    approval_days = Column(Float, nullable=True)
    custom_attributes = Column(JSON, nullable=True)


class InventorySnapshot(Base):
    __tablename__ = "inventory_snapshots"

    id = Column(String(36), primary_key=True, default=new_id)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    location_id = Column(String(36), ForeignKey("locations.id"), nullable=False)
    item_code = Column(String(100), nullable=False)
    item_description = Column(String(500), nullable=False)
    category = Column(String(150), nullable=False)
    stock_on_hand = Column(Float, nullable=False)
    reorder_level = Column(Float, nullable=False)
    max_stock_level = Column(Float, nullable=False)
    unit_cost = Column(Float, nullable=False)
    days_since_last_movement = Column(Integer, nullable=False, default=0)
    custom_attributes = Column(JSON, nullable=True)


class Invoice(Base):
    __tablename__ = "invoices"
    __table_args__ = (
        Index("uq_invoices_org_invoice_number", "org_id", "invoice_number", unique=True),
    )

    id = Column(String(36), primary_key=True, default=new_id)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    location_id = Column(String(36), ForeignKey("locations.id"), nullable=False)
    invoice_number = Column(String(100), nullable=False, index=True)
    po_number = Column(String(100), nullable=False)
    vendor_name = Column(String(255), nullable=False)
    invoice_amount = Column(Float, nullable=False)
    po_reference_amount = Column(Float, nullable=False)
    invoice_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=True)
    payment_status = Column(String(50), nullable=False, default="PENDING")


class BusinessRule(Base):
    __tablename__ = "business_rules"

    id = Column(String(36), primary_key=True, default=new_id)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    rule_code = Column(String(100), nullable=False)
    rule_name = Column(String(255), nullable=False)
    module = Column(String(100), nullable=False)
    metric = Column(String(100), nullable=False)
    operator = Column(String(20), nullable=False)
    threshold_value = Column(Float, nullable=False)
    severity = Column(String(50), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)


class OperationalException(Base):
    __tablename__ = "operational_exceptions"

    id = Column(String(36), primary_key=True, default=new_id)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    location_id = Column(String(36), ForeignKey("locations.id"), nullable=True)
    module = Column(String(100), nullable=False)
    severity = Column(String(50), nullable=False)
    title = Column(String(255), nullable=False)
    description = Column(String(1000), nullable=False)
    financial_impact = Column(Float, nullable=False, default=0)
    status = Column(String(50), nullable=False, default="OPEN")
    resolved_by = Column(String(255), nullable=True)


class ProcessEvent(Base):
    __tablename__ = "process_events"

    id = Column(String(36), primary_key=True, default=new_id)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    case_id = Column(String(100), nullable=False, index=True)
    activity_name = Column(String(150), nullable=False)
    actor = Column(String(255), nullable=False)
    event_timestamp = Column(DateTime, nullable=False)


class DataImport(Base):
    __tablename__ = "data_imports"

    id = Column(String(36), primary_key=True, default=new_id)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    file_name = Column(String(255), nullable=False)
    source_type = Column(String(100), nullable=False)
    records_processed = Column(Integer, nullable=False, default=0)
    status = Column(String(50), nullable=False)
    imported_by = Column(String(255), nullable=True)
    created_at = Column(DateTime, nullable=False)


class AutomationWorkflow(Base):
    __tablename__ = "automation_workflows"

    id = Column(String(36), primary_key=True, default=new_id)
    org_id = Column(String(36), ForeignKey("organizations.id"), nullable=False, index=True)
    workflow_name = Column(String(255), nullable=False)
    trigger_module = Column(String(100), nullable=False)
    trigger_severity = Column(String(50), nullable=False)
    action_type = Column(String(100), nullable=False)
    action_target = Column(String(255), nullable=False)
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, nullable=False)
