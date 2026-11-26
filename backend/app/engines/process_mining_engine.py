from collections import Counter, defaultdict

from app.models.erp_models import InventorySnapshot, OperationalException, ProcessEvent, PurchaseOrder


def analyze_process(db, org_id):
    events = (
        db.query(ProcessEvent)
        .filter(ProcessEvent.org_id == org_id)
        .order_by(ProcessEvent.case_id, ProcessEvent.event_timestamp)
        .all()
    )
    cases = defaultdict(list)
    for event in events:
        cases[event.case_id].append(event)
    variants = Counter()
    cycle_times = []
    rework_cases = 0
    for case_events in cases.values():
        variants[" -> ".join(event.activity_name for event in case_events)] += 1
        if any(event.activity_name == "APPROVAL_REJECTED" for event in case_events) and any(
            event.activity_name == "PR_RESUBMITTED" for event in case_events
        ):
            rework_cases += 1
        if len(case_events) > 1:
            cycle_times.append(
                (case_events[-1].event_timestamp - case_events[0].event_timestamp).total_seconds()
                / 3600
            )
    return {
        "cases_analyzed": len(cases),
        "execution_variants": [
            {"variant": variant, "cases": count}
            for variant, count in variants.most_common()
        ],
        "rework_rate_percent": round(100 * rework_cases / len(cases), 2) if cases else 0,
        "cycle_time_hours": {
            "average": round(sum(cycle_times) / len(cycle_times), 2) if cycle_times else None,
            "cases_with_multiple_events": len(cycle_times),
        },
    }


def simulate_improvements(db, org_id, approval_target_days=3, delivery_sla_days=0):
    pos = db.query(PurchaseOrder).filter(PurchaseOrder.org_id == org_id).all()
    inventory = db.query(InventorySnapshot).filter(InventorySnapshot.org_id == org_id).all()
    approval_exceptions = sum(
        (po.approval_days or 0) > approval_target_days for po in pos
    )
    late_exceptions = sum(
        po.actual_delivery_date is not None
        and po.expected_delivery_date is not None
        and (po.actual_delivery_date - po.expected_delivery_date).days > delivery_sla_days
        for po in pos
    )
    unlocked = sum(
        max(0, item.stock_on_hand - item.max_stock_level) * item.unit_cost for item in inventory
    )
    exception_count = (
        db.query(OperationalException)
        .filter(OperationalException.org_id == org_id, OperationalException.status == "OPEN")
        .count()
    )
    return {
        "estimate_only": True,
        "assumptions": [
            "Approval and delivery exceptions are counted from current PO records.",
            "Working capital unlocked assumes excess above max stock can be liquidated at unit cost.",
        ],
        "targets": {
            "approval_target_days": approval_target_days,
            "delivery_sla_days": delivery_sla_days,
        },
        "estimated_exceptions_eliminated": min(
            exception_count, approval_exceptions + late_exceptions
        ),
        "estimated_working_capital_unlocked": round(unlocked, 2),
    }
