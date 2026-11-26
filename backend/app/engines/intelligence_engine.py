from app.models.erp_models import InventorySnapshot, Invoice, PurchaseOrder


def _score(risk):
    return round(max(0, min(100, risk)), 1)


def build_intelligence(db, org_id, location_id=None):
    po_query = db.query(PurchaseOrder).filter(PurchaseOrder.org_id == org_id)
    inventory_query = db.query(InventorySnapshot).filter(InventorySnapshot.org_id == org_id)
    invoice_query = db.query(Invoice).filter(Invoice.org_id == org_id)
    if location_id:
        po_query = po_query.filter(PurchaseOrder.location_id == location_id)
        inventory_query = inventory_query.filter(InventorySnapshot.location_id == location_id)
        invoice_query = invoice_query.filter(Invoice.location_id == location_id)
    pos, items, invoices = po_query.all(), inventory_query.all(), invoice_query.all()

    vendors = {}
    for po in pos:
        record = vendors.setdefault(po.vendor_name, {"orders": [], "risk": 0, "actions": set()})
        record["orders"].append(po)
        if po.actual_delivery_date and po.expected_delivery_date:
            delay = (po.actual_delivery_date - po.expected_delivery_date).days
            if delay > 0:
                record["risk"] += min(35, delay * 3)
                record["actions"].add("Review supplier delivery SLA and recovery plan.")
        if (po.approval_days or 0) > 5:
            record["risk"] += min(20, (po.approval_days - 5) * 3)
            record["actions"].add("Remove purchase approval bottlenecks and monitor queue age.")
    for invoice in invoices:
        record = vendors.setdefault(invoice.vendor_name, {"orders": [], "risk": 0, "actions": set()})
        excess = invoice.invoice_amount - invoice.po_reference_amount
        if excess > 0:
            record["risk"] += min(45, excess / max(invoice.po_reference_amount, 1) * 100)
            record["actions"].add("Enforce three-way matching and keep disputed payment on hold.")
    vendor_scores = [
        {
            "vendor": name,
            "risk_score": _score(data["risk"]),
            "purchase_orders": len(data["orders"]),
            "prescriptive_actions": sorted(data["actions"])
            or ["Continue periodic supplier performance reviews."],
        }
        for name, data in sorted(vendors.items())
    ]
    item_scores = []
    for item in items:
        risk = 0
        actions = []
        if item.stock_on_hand < item.reorder_level:
            risk += 55
            actions.append("Expedite replenishment and confirm supplier availability.")
        if item.days_since_last_movement > 90:
            risk += min(45, (item.days_since_last_movement - 90) / 3)
            actions.append("Review demand, transfer usable stock, and prevent expiry or obsolescence.")
        item_scores.append(
            {
                "item_code": item.item_code,
                "item_description": item.item_description,
                "location_id": item.location_id,
                "risk_score": _score(risk),
                "prescriptive_actions": actions or ["Maintain current replenishment parameters."],
            }
        )
    return {"vendors": vendor_scores, "items": item_scores}
