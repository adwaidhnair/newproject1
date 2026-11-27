# Northstar ERP Operations Intelligence

Northstar is a multi-tenant operations intelligence platform for enterprise procurement, inventory, accounts payable and process performance. The project is built in phases around a canonical operational data model, explainable analytics and a responsive executive control tower.

## Product capabilities

- Tenant-aware operations views with industry and location context.
- Control tower KPIs: financial exposure, purchase-order spend, supplier OTIF, approval cycle time, inventory capital and invoice leakage risk.
- Configurable business rules that evaluate purchasing, inventory and invoice data into operational exceptions.
- Vendor and item risk scorecards with prescriptive next steps.
- Process mining for execution variants, approval rework and case cycle times, plus a clearly labeled what-if estimate.
- Workflow configuration, exception governance and CSV upload with preview, validation, tenant-safe upsert and import audit history.
- FMCG and manufacturing terminology profiles and seed data for two Kerala-based organizations.

## Architecture

```text
frontend/                    React + Vite executive control tower
  src/App.jsx                Tenant shell, navigation and nine modular views
  src/styles.css             Responsive design system with Tailwind CSS v4
backend/
  app/main.py                FastAPI routes and dependency wiring
  app/core/database.py       SQLAlchemy engine/session (SQLite default)
  app/models/erp_models.py   UUID-keyed canonical multi-tenant entities
  app/engines/               KPI, rules, risk intelligence and process mining
  app/connectors/csv_connector.py
                              CSV preview, validation, upsert and import audit
  app/profiles/              Industry-specific terminology and default rules
  seed_data.py               Reproducible starter tenants and anomaly scenarios
docs/                        Sample ERP exports and product documentation
```

The browser calls the versioned API at `http://localhost:8000/api/v1` by default. Set `VITE_API_URL` to point the UI at another API origin. Tenant IDs scope business queries; CSV imports additionally validate that referenced locations belong to the selected tenant. SQLite is convenient for local development; production should use PostgreSQL.

## Local development

### Requirements

- Python 3.10+
- Node.js 18+ and npm

### 1. Start the backend

```bash
cd backend
python -m venv .venv
# Windows PowerShell:
.venv\Scripts\Activate.ps1
# macOS/Linux:
# source .venv/bin/activate
python -m pip install -r requirements.txt
python seed_data.py
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

The API is available at `http://localhost:8000`; interactive OpenAPI docs are at `http://localhost:8000/docs`. Verify startup with `http://localhost:8000/api/v1/bootstrap`. The SQLite database is created as `backend/erp_intel.db` when commands run from `backend/`.

### 2. Start the frontend

In a second terminal:

```bash
cd frontend
npm install
npm run dev
```

Open `http://localhost:5173`. The development server is configured for that port and the backend CORS policy allows this origin.

### Production frontend build

```bash
cd frontend
npm run build
npm run preview
```

## CSV purchase order import

The Data Import view accepts CSV uploads. Map source headers to canonical field names in the wizard, preview and validate first, then ingest. Required fields include `po_number`, `location_id`, `vendor_name`, `item_code`, `item_description`, `quantity`, `unit_price`, `total_amount` and `order_date`. Dates use ISO `YYYY-MM-DD` format. `location_id` must be an ID belonging to the selected organization. Re-importing a PO number updates that tenant's record. Each import is audited and triggers rule re-evaluation.

See [`docs/sample_erp_pos.csv`](docs/sample_erp_pos.csv) for the sample header and row.

## Deployment baseline

For a small demo, [`render.yaml`](render.yaml) configures the API for Render,
and [`docs/deployment-vercel-render-neon.md`](docs/deployment-vercel-render-neon.md)
walks through deploying the frontend to Vercel and using Neon for PostgreSQL.
The free Render service may sleep when idle; free-plan limits and availability
can change. This setup is for demo data only, not sensitive business records or
production workloads.

The backend accepts `DATABASE_URL`, `AUTH_TOKEN_SECRET`,
`BOOTSTRAP_SETUP_TOKEN`, `CORS_ORIGINS`, `ENVIRONMENT`, and
`AUTO_CREATE_TABLES`. Keep secrets in the hosting provider's secret settings;
never commit them or place them in Vite build variables. Render runs the
Alembic migrations at startup and disables automatic table creation.
`docker-compose.yml` remains available for self-managed deployments.

## Security and production-readiness boundary

The app includes password-based accounts, HTTP-only sessions, first-owner
bootstrap, organization membership checks, and role-based access checks. This
is not an independent security audit or enterprise production certification.
Before using real business data, review tenant isolation and role enforcement,
add operational monitoring and tested backups, and complete an appropriate
security and privacy review. Validate tenant isolation for every new route and
migration.

## Roadmap

1. **Identity and access** — Complete SSO/OIDC, role-based authorization, organization membership, and immutable action audit history; current API-key support is only a deployment baseline.
2. **Production data platform** — Operate PostgreSQL migrations, enforce tenant isolation policies, and establish secrets management, backups, restore drills, and observability.
3. **Reliable ingestion** — ERP-specific connectors, asynchronous imports, schema mapping templates, row-level reconciliation and retry/dead-letter handling.
4. **Richer intelligence** — calibrated risk scoring, forecasted stockout and delivery risk, confidence explanations and feedback from resolved exceptions.
5. **Governed automation** — workflow versioning, approval gates, dry runs, event-driven execution and delivery observability.
6. **Executive reporting** — saved views, scheduled reports, exports, configurable targets and organization-specific KPI definitions.

## Current scope and operational notes

This is a development-stage foundation, not a production-hardened ERP integration. Seed data is illustrative. Risk scores and simulation outcomes are directional, not financial advice or guaranteed savings. Secure the API, configure a production database and review tenant authorization, data retention and audit requirements before deploying with real enterprise data.
