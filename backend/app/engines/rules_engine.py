from datetime import date

from app.models.erp_models import (
    BusinessRule,
    InventorySnapshot,
    Invoice,
    OperationalException,
    PurchaseOrder,
)

_OPERATORS = {
    ">": lambda left, right: left > right,
    ">=": lambda left, right: left >= right,
    "<": lambda left, right: left < right,
    "<=": lambda left, right: left <= right,
    "==": lambda left, right: left == right,
    "!=": lambda left, right: left != right,
}


def _metric_value(rule, record):
    metric = rule.metric
    if metric == "delivery_delay_days" and record.expected_delivery_date:
        actual = record.actual_delivery_date
        return ((actual or date.today()) - record.expected_delivery_date).days
    if metric == "approval_days":
        return record.approval_days or 0
    if metric == "stock_on_hand_vs_reorder_level":
        return record.stock_on_hand / record.reorder_level if record.reorder_level else float("inf")
    if metric == "days_since_last_movement":
        return record.days_since_last_movement
    if metric == "invoice_vs_po_amount":
        return record.invoice_amount - record.po_reference_amount
    return None


def evaluate_rules(db, org_id):
    models_by_module = {
        "PROCUREMENT": PurchaseOrder,
        "PURCHASE": PurchaseOrder,
        "INVENTORY": InventorySnapshot,
        "FINANCE": Invoice,
        "AP": Invoice,
    }
    # Regeneration is idempotent: retire generated open exceptions before rebuilding.
    db.query(OperationalException).filter(
        OperationalException.org_id == org_id,
        OperationalException.status == "OPEN",
    ).delete(synchronize_session=False)
    created = []
    rules = (
        db.query(BusinessRule)
        .filter(BusinessRule.org_id == org_id, BusinessRule.is_active.is_(True))
        .all()
    )
    for rule in rules:
        model = models_by_module.get(rule.module.upper())
        comparator = _OPERATORS.get(rule.operator)
        if not model or not comparator:
            continue
        records = db.query(model).filter(model.org_id == org_id).all()
        for record in records:
            value = _metric_value(rule, record)
            if value is None or not comparator(value, rule.threshold_value):
                continue
            if model is PurchaseOrder:
                location_id = record.location_id
                entity = record.po_number
                impact = record.total_amount or 0
            elif model is InventorySnapshot:
                location_id = record.location_id
                entity = record.item_code
                impact = max(0, record.reorder_level - record.stock_on_hand) * record.unit_cost
            else:
                location_id = record.location_id
                entity = record.invoice_number
                impact = max(0, record.invoice_amount - record.po_reference_amount)
            exc = OperationalException(
                org_id=org_id,
                location_id=location_id,
                module=rule.module,
                severity=rule.severity,
                title=f"{rule.rule_name}: {entity}",
                description=f"{rule.metric} evaluated to {value} {rule.operator} {rule.threshold_value}.",
                financial_impact=impact,
                status="OPEN",
            )
            db.add(exc)
            created.append(exc)
    db.flush()
    return created
