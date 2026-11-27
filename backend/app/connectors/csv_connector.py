import csv
import io
import re
import zipfile
from datetime import date, datetime
from pathlib import Path
from sqlalchemy.exc import IntegrityError

from app.engines.rules_engine import evaluate_rules
from app.models.erp_models import DataImport, Department, Location, PurchaseOrder

MAX_CSV_BYTES = 10 * 1024 * 1024
MAX_IMPORT_ROWS = 100_000
MAX_IMPORT_COLUMNS = 250

FIELD_ALIASES = {
    "po_number": {"po", "po no", "po number", "purchase order", "purchase order no", "purchase order number", "order number"},
    "location_id": {"location", "location id", "location code", "site", "plant", "warehouse", "facility"},
    "dept_id": {"department", "department id", "department code", "cost center", "cost centre"},
    "vendor_name": {"vendor", "vendor name", "supplier", "supplier name"},
    "item_code": {"item", "item code", "sku", "sku code", "part", "part number", "material code"},
    "item_description": {"item description", "description", "product description", "material description", "part description"},
    "quantity": {"qty", "quantity", "ordered quantity", "order quantity"},
    "unit_price": {"unit price", "price per unit", "unit cost", "rate", "price"},
    "total_amount": {"total", "total amount", "amount", "line amount", "line total", "order value", "po amount"},
    "order_date": {"order date", "po date", "purchase date", "created date"},
    "expected_delivery_date": {"expected delivery date", "promised delivery date", "delivery due date", "due date"},
    "actual_delivery_date": {"actual delivery date", "received date", "receipt date", "delivery date"},
    "approval_days": {"approval days", "approval duration", "approval time"},
}
SUPPORTED_FIELDS = frozenset(FIELD_ALIASES)


def _header_key(value):
    return re.sub(r"[^a-z0-9]+", " ", str(value or "").casefold()).strip()


def read_tabular_rows(content, file_name="upload.csv"):
    """Read bounded CSV/XLSX files into header-keyed rows without persisting uploads."""
    if len(content) > MAX_CSV_BYTES:
        raise ValueError("File exceeds the 10 MiB upload limit.")
    extension = Path(file_name or "upload.csv").suffix.casefold()
    if extension == ".xlsx":
        try:
            from openpyxl import load_workbook

            workbook = load_workbook(io.BytesIO(content), read_only=True, data_only=True)
        except (ImportError, OSError, ValueError, zipfile.BadZipFile) as exc:
            raise ValueError("Could not read this Excel file. Upload a valid .xlsx workbook.") from exc
        try:
            worksheet = workbook.active
            if worksheet.max_column and worksheet.max_column > MAX_IMPORT_COLUMNS:
                raise ValueError(f"Excel files may contain no more than {MAX_IMPORT_COLUMNS} columns.")
            iterator = worksheet.iter_rows(values_only=True, max_col=MAX_IMPORT_COLUMNS)
            raw_headers = next(iterator, None)
            if not raw_headers:
                raise ValueError("Excel sheet must include a header row.")
            headers = [str(value).strip() if value is not None else "" for value in raw_headers]
            while headers and not headers[-1]:
                headers.pop()
            if not headers or any(not header for header in headers):
                raise ValueError("Every column must have a non-empty header.")
            if len({_header_key(header) for header in headers}) != len(headers):
                raise ValueError("Column headers must be unique, ignoring capitalization and punctuation.")
            rows = []
            for line_number, values in enumerate(iterator, start=2):
                if line_number > MAX_IMPORT_ROWS + 1:
                    raise ValueError(f"Files may contain no more than {MAX_IMPORT_ROWS} data rows.")
                cells = list(values[:len(headers)])
                if not any(value is not None and str(value).strip() for value in cells):
                    continue
                row = {}
                for index, header in enumerate(headers):
                    value = cells[index] if index < len(cells) else None
                    if isinstance(value, datetime):
                        value = value.date().isoformat()
                    elif isinstance(value, date):
                        value = value.isoformat()
                    elif value is None:
                        value = ""
                    row[header] = str(value).strip()
                rows.append((line_number, row))
            return headers, rows
        finally:
            workbook.close()

    if extension != ".csv":
        raise ValueError("Unsupported file type. Upload a .csv or .xlsx file.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = content.decode("cp1252")
        except UnicodeDecodeError:
            text = content.decode("latin-1")
    sample = text[:8192]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    reader = csv.reader(io.StringIO(text), dialect)
    raw_headers = next(reader, None)
    if not raw_headers:
        raise ValueError("CSV must include a header row.")
    headers = [str(header).strip() for header in raw_headers]
    if any(not header for header in headers):
        raise ValueError("Every column must have a non-empty header.")
    if len({_header_key(header) for header in headers}) != len(headers):
        raise ValueError("Column headers must be unique, ignoring capitalization and punctuation.")
    if len(headers) > MAX_IMPORT_COLUMNS:
        raise ValueError(f"CSV files may contain no more than {MAX_IMPORT_COLUMNS} columns.")
    rows = []
    for line_number, values in enumerate(reader, start=2):
        if line_number > MAX_IMPORT_ROWS + 1:
            raise ValueError(f"Files may contain no more than {MAX_IMPORT_ROWS} data rows.")
        if not any(value.strip() for value in values):
            continue
        row = {header: values[index].strip() if index < len(values) else "" for index, header in enumerate(headers)}
        if len(values) > len(headers):
            row[None] = values[len(headers):]
        rows.append((line_number, row))
    return headers, rows


def _tenant_reference_lookup(db, model, org_id):
    records = db.query(model).filter(model.org_id == org_id).all()
    aliases = {}
    ambiguous = set()
    for record in records:
        for value in (record.id, getattr(record, "name", None)):
            if not value:
                continue
            key = value.strip().casefold()
            if key in aliases and aliases[key] != record.id:
                ambiguous.add(key)
            else:
                aliases[key] = record.id
    return aliases, ambiguous


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
    def _rows(content, mapping, file_name="upload.csv"):
        if isinstance(content, bytes):
            pass
        else:
            content = content.encode("utf-8")
        headers, source_rows = read_tabular_rows(content, file_name)
        if not isinstance(mapping, dict):
            raise ValueError("Column mapping must be a JSON object.")
        if len(set(mapping.values())) != len(mapping.values()):
            raise ValueError("Each destination field can only be mapped once.")
        mapped_fields = set(mapping.values())
        missing = CSVConnector.REQUIRED - mapped_fields
        if missing:
            raise ValueError(f"Column mapping is missing required fields: {', '.join(sorted(missing))}")
        result = []
        errors = []
        seen = set()
        for line, source in source_rows:
            if None in source:
                errors.append({"row": line, "error": "Row has more values than the file header."})
                continue
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
                allowed_fields = (
                    CSVConnector.REQUIRED
                    | CSVConnector.DATE_FIELDS
                    | CSVConnector.FLOAT_FIELDS
                    | {"dept_id"}
                )
                unsupported = set(row) - allowed_fields
                if unsupported:
                    raise ValueError(
                        f"Unsupported target fields: {', '.join(sorted(unsupported))}"
                    )
                for field in CSVConnector.FLOAT_FIELDS:
                    if row.get(field):
                        row[field] = float(row[field])
                for field in CSVConnector.DATE_FIELDS:
                    if row.get(field):
                        row[field] = date.fromisoformat(row[field])
                if row["quantity"] <= 0 or row["unit_price"] < 0 or row["total_amount"] < 0:
                    raise ValueError("quantity must be positive and amounts cannot be negative")
                if "approval_days" in row and row["approval_days"] < 0:
                    raise ValueError("approval_days cannot be negative")
                if row["total_amount"] != round(row["quantity"] * row["unit_price"], 2):
                    raise ValueError("total_amount must equal quantity multiplied by unit_price")
                result.append((line, row))
            except (ValueError, TypeError) as exc:
                errors.append({"row": line, "error": str(exc)})
        return result, errors

    @staticmethod
    def suggest_mapping(content, file_name="upload.csv"):
        headers, _ = read_tabular_rows(content, file_name)
        alias_targets = {
            alias: field
            for field, aliases in FIELD_ALIASES.items()
            for alias in aliases | {field.replace("_", " ")}
        }
        mapping = {}
        for header in headers:
            target = alias_targets.get(_header_key(header))
            if target and target not in mapping.values():
                mapping[header] = target
        missing_required = sorted(CSVConnector.REQUIRED - set(mapping.values()))
        return {
            "headers": headers,
            "mapping": mapping,
            "unmapped_headers": [header for header in headers if header not in mapping],
            "missing_required_fields": missing_required,
        }

    def preview(self, content, mapping, file_name="upload.csv", db=None, org_id=None):
        rows, errors = self._rows(content, mapping, file_name)
        if db is not None and org_id:
            locations, ambiguous_locations = _tenant_reference_lookup(db, Location, org_id)
            departments, ambiguous_departments = _tenant_reference_lookup(db, Department, org_id)
            for line, row in rows:
                location_key = row["location_id"].strip().casefold()
                location_id = locations.get(location_key)
                if location_id is None or location_key in ambiguous_locations:
                    errors.append({
                        "row": line,
                        "error": f"Unknown or ambiguous tenant location: {row['location_id']}",
                    })
                else:
                    row["location_id"] = location_id
                department_id = row.get("dept_id")
                department_key = department_id.strip().casefold() if department_id else ""
                if department_key and (
                    department_key not in departments or department_key in ambiguous_departments
                ):
                    errors.append({
                        "row": line,
                        "error": f"Unknown or ambiguous tenant department: {department_id}",
                    })
                elif department_id:
                    row["dept_id"] = departments[department_key]
        error_rows = {error["row"] for error in errors if error["row"] is not None}
        valid_rows = sum(1 for line, _ in rows if line not in error_rows)
        return {
            "valid_rows": valid_rows,
            "errors": errors,
            "sample": [
                {
                    key: value.isoformat() if isinstance(value, date) else value
                    for key, value in row.items()
                }
                for _, row in rows[:5]
            ],
        }

    def ingest(self, db, org_id, content, file_name, mapping, imported_by=None):
        rows, errors = self._rows(content, mapping, file_name)
        if errors:
            raise ValueError(
                f"Import has {len(errors)} validation issue(s). Fix them and preview the file again."
            )
        file_name = Path(file_name or "upload.csv").name[:255]
        imported_by = imported_by[:255] if imported_by else None
        locations, ambiguous_locations = _tenant_reference_lookup(db, Location, org_id)
        departments, ambiguous_departments = _tenant_reference_lookup(db, Department, org_id)
        for line, row in rows:
            location_key = row["location_id"].strip().casefold()
            if location_key not in locations or location_key in ambiguous_locations:
                raise ValueError(
                    f"Row {line} has an unknown or ambiguous tenant location: "
                    f"{row['location_id']}. No records were imported."
                )
            row["location_id"] = locations[location_key]
            department_id = row.get("dept_id")
            if department_id:
                department_key = department_id.strip().casefold()
                normalized_department_id = departments.get(department_key)
                if normalized_department_id is None or department_key in ambiguous_departments:
                    raise ValueError(
                        f"Row {line} has an unknown or ambiguous tenant department: "
                        f"{department_id}. No records were imported."
                    )
                row["dept_id"] = normalized_department_id
        processed = 0
        for _, row in rows:
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
            source_type=Path(file_name).suffix.lstrip(".").upper() or "CSV",
            records_processed=processed,
            status="COMPLETED" if not errors else "COMPLETED_WITH_ERRORS",
            imported_by=imported_by,
            created_at=datetime.utcnow(),
        )
        db.add(audit)
        try:
            db.commit()
        except IntegrityError:
            db.rollback()
            raise ValueError(
                "A purchase order number already exists for this organization."
            ) from None
        return {
            "import_id": audit.id,
            "records_processed": processed,
            "errors": errors,
            "status": audit.status,
        }
