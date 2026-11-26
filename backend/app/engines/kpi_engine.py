from sqlalchemy import func

from app.models.erp_models import (
    InventorySnapshot,
    Invoice,
    OperationalException,
    PurchaseOrder,
)


def _scope(query, model, org_id, location_id=None):
    query = query.filter(model.org_id == org_id)
    if location_id and hasattr(model, "location_id"):
        query = query.filter(model.location_id == location_id)
    return query


def compute_kpis(db, org_id, location_id=None):
    pos = _scope(db.query(PurchaseOrder), PurchaseOrder, org_id, location_id).all()
    inventory = _scope(db.query(InventorySnapshot), InventorySnapshot, org_id, location_id).all()
    invoices = _scope(db.query(Invoice), Invoice, org_id, location_id).all()
    open_exceptions = _scope(
        db.query(OperationalException), OperationalException, org_id, location_id
    ).filter(OperationalException.status == "OPEN").all()

    delivered = [po for po in pos if po.actual_delivery_date and po.expected_delivery_date]
    on_time = sum(po.actual_delivery_date <= po.expected_delivery_date for po in delivered)
    leakage_risk = sum(max(0, invoice.invoice_amount - invoice.po_reference_amount) for invoice in invoices)
    reliability = {}
    for vendor in sorted({po.vendor_name for po in pos}):
        vendor_pos = [po for po in pos if po.vendor_name == vendor]
        vendor_delivered = [
            po for po in vendor_pos if po.actual_delivery_date and po.expected_delivery_date
        ]
        reliability[vendor] = {
            "purchase_orders": len(vendor_pos),
            "otif_percent": round(
                100
                * sum(po.actual_delivery_date <= po.expected_delivery_date for po in vendor_delivered)
                / len(vendor_delivered),
                2,
            )
            if vendor_delivered
            else None,
            "avg_approval_days": round(
                sum(po.approval_days or 0 for po in vendor_pos) / len(vendor_pos), 2
            ),
        }

    return {
        "total_financial_exposure": round(sum(exc.financial_impact or 0 for exc in open_exceptions), 2),
        "po_spend": round(sum(po.total_amount or 0 for po in pos), 2),
        "otif_percent": round(100 * on_time / len(delivered), 2) if delivered else None,
        "avg_approval_days": round(
            sum(po.approval_days or 0 for po in pos) / len(pos), 2
        )
        if pos
        else None,
        "inventory_capital": round(
            sum(item.stock_on_hand * item.unit_cost for item in inventory), 2
        ),
        "stockout_alerts": sum(item.stock_on_hand < item.reorder_level for item in inventory),
        "three_way_invoice_leakage_risk": round(leakage_risk, 2),
        "vendor_reliability_scorecards": reliability,
        "location_id": location_id,
    }
