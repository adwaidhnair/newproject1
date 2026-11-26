import json
import os
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import Depends, FastAPI, File, Form, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.connectors.csv_connector import CSVConnector
from app.core.database import Base, engine, get_db
from app.core.security import get_configured_api_key, require_api_key
from app.engines.intelligence_engine import build_intelligence
from app.engines.kpi_engine import compute_kpis
from app.engines.process_mining_engine import analyze_process, simulate_improvements
from app.engines.rules_engine import evaluate_rules
from app.models.erp_models import (
    AutomationWorkflow,
    BusinessRule,
    DataImport,
    Department,
    InventorySnapshot,
    Invoice,
    Location,
    OperationalException,
    Organization,
    PurchaseOrder,
)

@asynccontextmanager
async def lifespan(_app):
    get_configured_api_key()
    if os.getenv("AUTO_CREATE_TABLES", "true").lower() in {"1", "true", "yes"}:
        Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="Enterprise ERP Operations Intelligence Platform",
    version="1.0.0",
    docs_url=None if os.getenv("ENVIRONMENT", "development").lower() in {"production", "prod"} else "/docs",
    redoc_url=None if os.getenv("ENVIRONMENT", "development").lower() in {"production", "prod"} else "/redoc",
    lifespan=lifespan,
)
cors_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173").split(",")
    if origin.strip()
]
app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins,
    allow_credentials="*" not in cors_origins,
    allow_methods=["*"],
    allow_headers=["*"],
)
csv_connector = CSVConnector()


@app.middleware("http")
async def authenticate_api_requests(request, call_next):
    if request.url.path.startswith("/api/v1/"):
        try:
            require_api_key(request.headers.get("authorization"), request.headers.get("x-api-key"))
        except HTTPException as exc:
            return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})
    return await call_next(request)


@app.middleware("http")
async def limit_request_body_size(request, call_next):
    content_length = request.headers.get("content-length")
    if content_length:
        try:
            if int(content_length) > 10 * 1024 * 1024:
                return JSONResponse(status_code=413, content={"detail": "Request body exceeds 10 MiB"})
        except ValueError:
            return JSONResponse(status_code=400, content={"detail": "Invalid Content-Length header"})
    if request.url.path.startswith("/api/v1/connectors/csv/") and not content_length:
        return JSONResponse(
            status_code=411,
            content={"detail": "Content-Length is required for CSV uploads"},
        )
    return await call_next(request)


class RuleUpdate(BaseModel):
    rule_name: Optional[str] = None
    module: Optional[str] = None
    metric: Optional[str] = None
    operator: Optional[str] = None
    threshold_value: Optional[float] = None
    severity: Optional[str] = None
    is_active: Optional[bool] = None


class ExceptionUpdate(BaseModel):
    status: str = Field(min_length=1)
    resolved_by: Optional[str] = None


class SimulationRequest(BaseModel):
    approval_target_days: float = 3
    delivery_sla_days: int = 0


def _not_found_or_tenant(db, model, record_id, org_id):
    record = db.query(model).filter(model.id == record_id, model.org_id == org_id).one_or_none()
    if not record:
        raise HTTPException(status_code=404, detail="Record not found for this organization")
    return record


def _validate_location(db, org_id, location_id):
    if location_id and not db.query(Location.id).filter(
        Location.id == location_id, Location.org_id == org_id
    ).first():
        raise HTTPException(status_code=404, detail="Location not found for this organization")


@app.get("/api/v1/bootstrap")
def bootstrap(db: Session = Depends(get_db)):
    organizations = db.query(Organization).all()
    return {
        "organizations": [
            {
                "id": org.id,
                "name": org.name,
                "industry_type": org.industry_type,
                "base_currency": org.base_currency,
            }
            for org in organizations
        ],
        "seeded": bool(organizations),
    }


@app.get("/api/v1/organizations")
def organizations(db: Session = Depends(get_db)):
    return db.query(Organization).all()


@app.get("/api/v1/tenant-context/{org_id}")
def tenant_context(org_id: str, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == org_id).one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {
        "organization": org,
        "locations": db.query(Location).filter(Location.org_id == org_id).all(),
        "departments": db.query(Department).filter(Department.org_id == org_id).all(),
    }


@app.get("/api/v1/organization/{org_id}/industry")
def organization_industry(org_id: str, db: Session = Depends(get_db)):
    org = db.query(Organization).filter(Organization.id == org_id).one_or_none()
    if not org:
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"industry_type": org.industry_type, "industry_config": org.industry_config or {}}


@app.get("/api/v1/control-tower/{org_id}")
def control_tower(org_id: str, location_id: Optional[str] = None, db: Session = Depends(get_db)):
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    _validate_location(db, org_id, location_id)
    return compute_kpis(db, org_id, location_id)


@app.get("/api/v1/intelligence/{org_id}")
def intelligence(org_id: str, location_id: Optional[str] = None, db: Session = Depends(get_db)):
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    _validate_location(db, org_id, location_id)
    return build_intelligence(db, org_id, location_id)


@app.get("/api/v1/process-mining/{org_id}")
def process_mining(org_id: str, db: Session = Depends(get_db)):
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    return analyze_process(db, org_id)


@app.post("/api/v1/simulate/{org_id}")
def simulate(org_id: str, request: SimulationRequest, db: Session = Depends(get_db)):
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    return simulate_improvements(
        db, org_id, request.approval_target_days, request.delivery_sla_days
    )


@app.get("/api/v1/rules/{org_id}")
def rules(org_id: str, db: Session = Depends(get_db)):
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    return db.query(BusinessRule).filter(BusinessRule.org_id == org_id).all()


@app.patch("/api/v1/rules/{rule_id}")
def update_rule(
    rule_id: str, update: RuleUpdate, org_id: str, db: Session = Depends(get_db)
):
    rule = _not_found_or_tenant(db, BusinessRule, rule_id, org_id)
    for field, value in update.model_dump(exclude_unset=True).items():
        setattr(rule, field, value)
    evaluate_rules(db, rule.org_id)
    db.commit()
    return rule


@app.post("/api/v1/rules/{org_id}/evaluate")
def reevaluate_rules(org_id: str, db: Session = Depends(get_db)):
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    return {"exceptions_generated": len(evaluate_rules(db, org_id))}


@app.get("/api/v1/workflows/{org_id}")
def workflows(org_id: str, db: Session = Depends(get_db)):
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    return (
        db.query(AutomationWorkflow)
        .filter(AutomationWorkflow.org_id == org_id)
        .order_by(AutomationWorkflow.created_at.desc())
        .all()
    )


@app.post("/api/v1/workflows/{org_id}")
def create_workflow(org_id: str, workflow: dict, db: Session = Depends(get_db)):
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    allowed = {
        "workflow_name",
        "trigger_module",
        "trigger_severity",
        "action_type",
        "action_target",
        "is_active",
    }
    if not all(workflow.get(field) for field in allowed - {"is_active"}):
        raise HTTPException(status_code=422, detail="Workflow requires trigger and action fields")
    record = AutomationWorkflow(org_id=org_id, **{key: value for key, value in workflow.items() if key in allowed})
    db.add(record)
    db.commit()
    db.refresh(record)
    return record


@app.get("/api/v1/exceptions/{org_id}/list")
def list_exceptions(org_id: str, db: Session = Depends(get_db)):
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    return (
        db.query(OperationalException)
        .filter(OperationalException.org_id == org_id)
        .order_by(OperationalException.status, OperationalException.severity)
        .all()
    )


@app.patch("/api/v1/exceptions/{exc_id}")
def update_exception(
    exc_id: str, update: ExceptionUpdate, org_id: str, db: Session = Depends(get_db)
):
    exc = _not_found_or_tenant(db, OperationalException, exc_id, org_id)
    status = update.status.upper()
    if status not in {"OPEN", "IN_PROGRESS", "RESOLVED", "DISMISSED"}:
        raise HTTPException(status_code=422, detail="Unsupported exception status")
    exc.status = status
    exc.resolved_by = update.resolved_by
    db.commit()
    return exc


@app.get("/api/v1/imports/{org_id}")
def imports(org_id: str, db: Session = Depends(get_db)):
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    return (
        db.query(DataImport)
        .filter(DataImport.org_id == org_id)
        .order_by(DataImport.created_at.desc())
        .all()
    )


@app.get("/api/v1/procurement/{org_id}")
def procurement(org_id: str, location_id: Optional[str] = None, db: Session = Depends(get_db)):
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    _validate_location(db, org_id, location_id)
    query = db.query(PurchaseOrder).filter(PurchaseOrder.org_id == org_id)
    if location_id:
        query = query.filter(PurchaseOrder.location_id == location_id)
    return query.order_by(PurchaseOrder.order_date.desc()).all()


@app.get("/api/v1/inventory-invoices/{org_id}")
def inventory_invoices(
    org_id: str, location_id: Optional[str] = None, db: Session = Depends(get_db)
):
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    _validate_location(db, org_id, location_id)
    inventory_query = db.query(InventorySnapshot).filter(InventorySnapshot.org_id == org_id)
    invoice_query = db.query(Invoice).filter(Invoice.org_id == org_id)
    if location_id:
        inventory_query = inventory_query.filter(InventorySnapshot.location_id == location_id)
        invoice_query = invoice_query.filter(Invoice.location_id == location_id)
    return {
        "inventory": inventory_query.all(),
        "invoices": invoice_query.all(),
    }


async def _upload_payload(file: UploadFile, mapping: str):
    try:
        parsed_mapping = json.loads(mapping)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=422, detail="mapping must be a JSON object") from exc
    if not isinstance(parsed_mapping, dict) or not all(
        isinstance(key, str) and isinstance(value, str)
        for key, value in parsed_mapping.items()
    ):
        raise HTTPException(status_code=422, detail="mapping must map CSV column names to model fields")
    content = await file.read(10 * 1024 * 1024 + 1)
    if len(content) > 10 * 1024 * 1024:
        raise HTTPException(status_code=413, detail="CSV exceeds the 10 MiB upload limit")
    return content, parsed_mapping


@app.post("/api/v1/connectors/csv/preview")
async def csv_preview(
    file: UploadFile = File(...),
    mapping: str = Form(...),
):
    try:
        content, parsed_mapping = await _upload_payload(file, mapping)
        return csv_connector.preview(content, parsed_mapping)
    except (UnicodeDecodeError, ValueError) as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc


@app.post("/api/v1/connectors/csv/ingest/{org_id}")
async def csv_ingest(
    org_id: str,
    file: UploadFile = File(...),
    mapping: str = Form(...),
    imported_by: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    if not db.query(Organization.id).filter(Organization.id == org_id).first():
        raise HTTPException(status_code=404, detail="Organization not found")
    try:
        content, parsed_mapping = await _upload_payload(file, mapping)
        return csv_connector.ingest(
            db,
            org_id,
            content,
            file.filename or "upload.csv",
            parsed_mapping,
            imported_by,
        )
    except (UnicodeDecodeError, ValueError) as exc:
        db.rollback()
        raise HTTPException(status_code=422, detail=str(exc)) from exc
