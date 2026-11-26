import csv
import io
from datetime import date, datetime

from app.engines.rules_engine import evaluate_rules
from app.models.erp_models import DataImport, Location, PurchaseOrder


class BaseConnector:
    def preview(self, content, mapping):
        raise NotImplementedError

    def ingest(self, db, org_id, content, file_name, mapping, imported_by=None):
        raise NotImplementedError


class CSVConnector(BaseConnector):
    REQUIRED = {
        "po_number",
        "location_id",
        "vendor_name",
        "item_code",
        "item_description",
        "quantity",
        "unit_price",
        "total_amount",
        "order_date",
    }
    DATE_FIELDS = {"order_date", "expected_delivery_date", "actual_delivery_date"}
    FLOAT_FIELDS = {"quantity", "unit_price", "total_amount", "approval_days"}

    @staticmethod
    def _rows(content, mapping):
        if isinstance(content, bytes):
            content = content.decode("utf-8-sig")
        reader = csv.DictReader(io.StringIO(content))
        if not reader.fieldnames:
            raise ValueError("CSV must include a header row.")
        mapped_fields = set(mapping.values())
        missing = CSVConnector.REQUIRED - mapped_fields
        if missing:
            raise ValueError(f"Column mapping is missing required fields: {', '.join(sorted(missing))}")
        result = []
        errors = []
        seen = set()
        for line, source in enumerate(reader, start=2):
            row = {
                target: (source.get(column) or "").strip()
                for column, target in mapping.items()
            }
            if not any(row.values()):
                continue
            key = row.get("po_number")
            if key in seen:
                errors.append({"row": line, "error": f"Duplicate PO number in file: {key}"})
                continue
            seen.add(key)
            try:
                for field in CSVConnector.REQUIRED:
                    if not row.get(field):
                        raise ValueError(f"Missing value for {field}")
                for field in CSVConnector.FLOAT_FIELDS:
                    if row.get(field):
                        row[field] = float(row[field])
                for field in CSVConnector.DATE_FIELDS:
                    if row.get(field):
                        row[field] = date.fromisoformat(row[field])
                if row["quantity"] <= 0 or row["unit_price"] < 0 or row["total_amount"] < 0:
                    raise ValueError("quantity must be positive and amounts cannot be negative")
                result.append(row)
            except (ValueError, TypeError) as exc:
                errors.append({"row": line, "error": str(exc)})
        return result, errors

    def preview(self, content, mapping):
        rows, errors = self._rows(content, mapping)
        return {
            "valid_rows": len(rows),
            "errors": errors,
            "sample": [
                {
                    key: value.isoformat() if isinstance(value, date) else value
                    for key, value in row.items()
                }
                for row in rows[:5]
            ],
        }

    def ingest(self, db, org_id, content, file_name, mapping, imported_by=None):
        rows, errors = self._rows(content, mapping)
        locations = {
            location.id
            for location in db.query(Location).filter(Location.org_id == org_id).all()
        }
        processed = 0
        for row in rows:
            if row["location_id"] not in locations:
                errors.append({"row": None, "error": f"Unknown tenant location: {row['location_id']}"})
                continue
            po = (
                db.query(PurchaseOrder)
                .filter(PurchaseOrder.org_id == org_id, PurchaseOrder.po_number == row["po_number"])
                .one_or_none()
            )
            if po is None:
                po = PurchaseOrder(org_id=org_id, **row)
                db.add(po)
            else:
                for field, value in row.items():
                    setattr(po, field, value)
            processed += 1
        db.flush()
        evaluate_rules(db, org_id)
        audit = DataImport(
            org_id=org_id,
            file_name=file_name,
            source_type="CSV",
            records_processed=processed,
            status="COMPLETED" if not errors else "COMPLETED_WITH_ERRORS",
            imported_by=imported_by,
            created_at=datetime.utcnow(),
        )
        db.add(audit)
        db.commit()
        return {
            "import_id": audit.id,
            "records_processed": processed,
            "errors": errors,
            "status": audit.status,
        }
