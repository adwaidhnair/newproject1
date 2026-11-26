import json
from datetime import date, datetime, timedelta
from pathlib import Path

from app.core.database import Base, SessionLocal, engine
from app.models.erp_models import (
    AutomationWorkflow,
    BusinessRule,
    Department,
    InventorySnapshot,
    Invoice,
    Location,
    OperationalException,
    Organization,
    ProcessEvent,
    PurchaseOrder,
)

PROFILE_DIR = Path(__file__).parent / "app" / "profiles"


def load_profile(name):
    with (PROFILE_DIR / name).open(encoding="utf-8") as profile_file:
        return json.load(profile_file)


def seed():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    try:
        if db.query(Organization).count():
            print("Database already contains organizations; seed data left unchanged.")
            return

        fmcg_config = load_profile("fmcg.json")
        manufacturing_config = load_profile("manufacturing.json")
        apex = Organization(
            name="Apex Consumer Brands Ltd.",
            industry_type="FMCG",
            base_currency="INR",
            industry_config=fmcg_config,
        )
        kochi_precision = Organization(
            name="Kochi Precision Engineering Ltd.",
            industry_type="MANUFACTURING",
            base_currency="INR",
            industry_config=manufacturing_config,
        )
        db.add_all([apex, kochi_precision])
        db.flush()

        apex_locations = [
            Location(org_id=apex.id, name="Kochi", location_type="DISTRIBUTION_HUB", region="Kerala"),
            Location(org_id=apex.id, name="Thrissur", location_type="DISTRIBUTION_HUB", region="Kerala"),
            Location(org_id=apex.id, name="Trivandrum", location_type="DISTRIBUTION_HUB", region="Kerala"),
        ]
        plant = Location(
            org_id=kochi_precision.id,
            name="CNC Machining Plant",
            location_type="MANUFACTURING_PLANT",
            region="Kerala",
        )
        db.add_all(apex_locations + [plant])
        departments = [
            Department(org_id=apex.id, name="Procurement"),
            Department(org_id=apex.id, name="Supply Chain"),
            Department(org_id=kochi_precision.id, name="Production"),
            Department(org_id=kochi_precision.id, name="Procurement"),
        ]
        db.add_all(departments)
        db.flush()

        today = date.today()
        late_po = PurchaseOrder(
            org_id=apex.id,
            location_id=apex_locations[0].id,
            dept_id=departments[0].id,
            po_number="APX-PO-2025-0142",
            vendor_name="Malabar Packaging Industries",
            item_code="PKG-500ML",
            item_description="500 ml beverage bottles",
            quantity=50000,
            unit_price=2.4,
            total_amount=120000,
            order_date=today - timedelta(days=35),
            expected_delivery_date=today - timedelta(days=10),
            actual_delivery_date=today - timedelta(days=4),
            approval_days=6,
            custom_attributes={"pack_size": "500 ml", "rework_count": 1},
        )
        delayed_approval = PurchaseOrder(
            org_id=kochi_precision.id,
            location_id=plant.id,
            dept_id=departments[2].id,
            po_number="KPE-PO-2025-0087",
            vendor_name="Coimbatore Carbide Tools",
            item_code="TOOL-CARB-12",
            item_description="12 mm carbide end mills",
            quantity=40,
            unit_price=8500,
            total_amount=340000,
            order_date=today - timedelta(days=18),
            expected_delivery_date=today + timedelta(days=12),
            approval_days=9,
            custom_attributes={"machine_cell": "CNC-02"},
        )
        db.add_all([late_po, delayed_approval])
        db.flush()

        db.add_all(
            [
                InventorySnapshot(
                    org_id=apex.id,
                    location_id=apex_locations[1].id,
                    item_code="OIL-1L",
                    item_description="Edible oil, 1 litre pouch",
                    category="Packaged Foods",
                    stock_on_hand=80,
                    reorder_level=300,
                    max_stock_level=1800,
                    unit_cost=105,
                    days_since_last_movement=3,
                ),
                InventorySnapshot(
                    org_id=apex.id,
                    location_id=apex_locations[2].id,
                    item_code="JUICE-MANGO-1L",
                    item_description="Mango juice, 1 litre carton",
                    category="Beverages",
                    stock_on_hand=720,
                    reorder_level=250,
                    max_stock_level=1200,
                    unit_cost=68,
                    days_since_last_movement=146,
                    custom_attributes={"batch": "TVM-MJ-2403", "expiry_risk": "HIGH"},
                ),
                InventorySnapshot(
                    org_id=kochi_precision.id,
                    location_id=plant.id,
                    item_code="BRG-6204",
                    item_description="Deep-groove ball bearing 6204",
                    category="Machine Spares",
                    stock_on_hand=4,
                    reorder_level=12,
                    max_stock_level=60,
                    unit_cost=420,
                    days_since_last_movement=7,
                ),
                InventorySnapshot(
                    org_id=kochi_precision.id,
                    location_id=plant.id,
                    item_code="STEEL-SS316-ROD",
                    item_description="SS316 stainless steel rod, 20 mm",
                    category="Raw Materials",
                    stock_on_hand=950,
                    reorder_level=100,
                    max_stock_level=700,
                    unit_cost=310,
                    days_since_last_movement=211,
                    custom_attributes={"heat_number": "SS316-H8821"},
                ),
            ]
        )
        db.add(
            Invoice(
                org_id=apex.id,
                location_id=apex_locations[0].id,
                invoice_number="MPI-INV-88401",
                po_number=late_po.po_number,
                vendor_name=late_po.vendor_name,
                invoice_amount=132000,
                po_reference_amount=120000,
                invoice_date=today - timedelta(days=5),
                due_date=today + timedelta(days=25),
                payment_status="ON_HOLD",
            )
        )

        for organization, profile in ((apex, fmcg_config), (kochi_precision, manufacturing_config)):
            db.add_all(
                [
                    BusinessRule(org_id=organization.id, **rule)
                    for rule in profile["default_rules"]
                ]
            )
        db.add_all(
            [
                OperationalException(
                    org_id=apex.id,
                    location_id=apex_locations[0].id,
                    module="PROCUREMENT",
                    severity="HIGH",
                    title="Supplier delivery arrived late",
                    description=f"{late_po.po_number} arrived 6 days after its promised date.",
                    financial_impact=18000,
                    status="OPEN",
                ),
                OperationalException(
                    org_id=apex.id,
                    location_id=apex_locations[1].id,
                    module="INVENTORY",
                    severity="CRITICAL",
                    title="Edible oil below reorder level",
                    description="OIL-1L stock is 220 units below the reorder point.",
                    financial_impact=23100,
                    status="OPEN",
                ),
                OperationalException(
                    org_id=apex.id,
                    location_id=apex_locations[0].id,
                    module="FINANCE",
                    severity="CRITICAL",
                    title="Three-way match overbilling",
                    description="Invoice MPI-INV-88401 exceeds its PO reference by INR 12,000.",
                    financial_impact=12000,
                    status="OPEN",
                ),
                OperationalException(
                    org_id=kochi_precision.id,
                    location_id=plant.id,
                    module="PROCUREMENT",
                    severity="MEDIUM",
                    title="Purchase approval rework delay",
                    description=f"{delayed_approval.po_number} required rework and took 9 approval days.",
                    financial_impact=25000,
                    status="OPEN",
                ),
            ]
        )

        base_time = datetime.utcnow() - timedelta(days=3)
        db.add_all(
            [
                ProcessEvent(
                    org_id=kochi_precision.id,
                    case_id=delayed_approval.po_number,
                    activity_name=activity,
                    actor=actor,
                    event_timestamp=base_time + timedelta(hours=hours),
                )
                for activity, actor, hours in [
                    ("PR_CREATED", "anita.nair", 0),
                    ("APPROVAL_SUBMITTED", "anita.nair", 2),
                    ("APPROVAL_REJECTED", "rajesh.menon", 8),
                    ("PR_RESUBMITTED", "anita.nair", 14),
                    ("APPROVAL_SUBMITTED", "anita.nair", 15),
                    ("APPROVAL_APPROVED", "rajesh.menon", 26),
                    ("PO_ISSUED", "erp-system", 27),
                ]
            ]
        )
        db.add_all(
            [
                AutomationWorkflow(
                    org_id=apex.id,
                    workflow_name="Escalate critical stock breach",
                    trigger_module="INVENTORY",
                    trigger_severity="CRITICAL",
                    action_type="NOTIFY",
                    action_target="supply-chain-lead",
                    is_active=True,
                    created_at=datetime.utcnow(),
                ),
                AutomationWorkflow(
                    org_id=apex.id,
                    workflow_name="Hold overbilled invoices",
                    trigger_module="FINANCE",
                    trigger_severity="CRITICAL",
                    action_type="PLACE_PAYMENT_HOLD",
                    action_target="accounts-payable",
                    is_active=True,
                    created_at=datetime.utcnow(),
                ),
                AutomationWorkflow(
                    org_id=kochi_precision.id,
                    workflow_name="Escalate delayed approvals",
                    trigger_module="PROCUREMENT",
                    trigger_severity="MEDIUM",
                    action_type="NOTIFY",
                    action_target="procurement-manager",
                    is_active=True,
                    created_at=datetime.utcnow(),
                ),
            ]
        )

        db.commit()
        print("Seeded ERP Intelligence tenants and anomaly data successfully.")
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    seed()
