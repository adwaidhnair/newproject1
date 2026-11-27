import json
import os
import sys
import tempfile
import unittest
from io import BytesIO
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.core.auth import issue_access_token, verify_password
from app.core.database import Base, get_db
from app.main import app
from app.models.auth_models import OrganizationMembership, User
from app.models.erp_models import (
    BusinessRule,
    DataImport,
    Location,
    OperationalException,
    Organization,
    PurchaseOrder,
)


class TenantUpdateTests(unittest.TestCase):
    def setUp(self):
        self.auth_patch = patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "ERP_API_KEY": "",
                "AUTH_TOKEN_SECRET": "tenant-update-test-secret-that-is-long-enough",
            },
        )
        self.auth_patch.start()
        self.temp_dir = tempfile.TemporaryDirectory()
        database_path = os.path.join(self.temp_dir.name, "test.db")
        self.engine = create_engine(
            f"sqlite:///{database_path}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_factory = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)

        with self.session_factory() as db:
            db.add_all(
                [
                    Organization(id="org-a", name="Org A", industry_type="FMCG"),
                    Organization(id="org-b", name="Org B", industry_type="FMCG"),
                    Location(
                        id="loc-a",
                        org_id="org-a",
                        name="Kochi",
                        location_type="WAREHOUSE",
                        region="Kerala",
                    ),
                    User(
                        id="test-user",
                        email="test@example.com",
                        username="test-user",
                        password_hash="unused",
                        full_name="Test User",
                    ),
                    User(
                        id="viewer-user",
                        email="viewer@example.com",
                        username="viewer-user",
                        password_hash="unused",
                        full_name="Viewer User",
                    ),
                    OrganizationMembership(
                        id="membership-a", user_id="test-user", org_id="org-a", role="owner"
                    ),
                    OrganizationMembership(
                        id="membership-b", user_id="test-user", org_id="org-b", role="owner"
                    ),
                    OrganizationMembership(
                        id="membership-viewer", user_id="viewer-user", org_id="org-a", role="viewer"
                    ),
                    BusinessRule(
                        id="rule-a",
                        org_id="org-a",
                        rule_code="RULE-A",
                        rule_name="Rule A",
                        module="PROCUREMENT",
                        metric="total_amount",
                        operator=">",
                        threshold_value=100,
                        severity="HIGH",
                        is_active=True,
                    ),
                    OperationalException(
                        id="exception-a",
                        org_id="org-a",
                        module="PROCUREMENT",
                        severity="HIGH",
                        title="Exception A",
                        description="Test exception",
                        financial_impact=100,
                        status="OPEN",
                    ),
                ]
            )
            db.commit()

        def override_get_db():
            with self.session_factory() as db:
                yield db

        app.dependency_overrides[get_db] = override_get_db
        self.client = TestClient(app)
        self.headers = {
            "Authorization": f"Bearer {issue_access_token('test-user', 0)}",
        }

    def tearDown(self):
        app.dependency_overrides.clear()
        self.auth_patch.stop()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_rule_cannot_be_updated_through_another_organizations_scope(self):
        response = self.client.patch(
            "/api/v1/rules/rule-a?org_id=org-b",
            json={"severity": "CRITICAL"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 404)
        with self.session_factory() as db:
            self.assertEqual(
                db.query(BusinessRule).filter_by(id="rule-a").one().severity,
                "HIGH",
            )

    def test_rule_can_be_updated_in_its_own_organization(self):
        with patch("app.main.evaluate_rules", return_value=[]):
            response = self.client.patch(
                "/api/v1/rules/rule-a?org_id=org-a",
                json={"severity": "CRITICAL"},
                headers=self.headers,
            )

        self.assertEqual(response.status_code, 200)
        with self.session_factory() as db:
            self.assertEqual(
                db.query(BusinessRule).filter_by(id="rule-a").one().severity,
                "CRITICAL",
            )

    def test_exception_cannot_be_updated_through_another_organizations_scope(self):
        response = self.client.patch(
            "/api/v1/exceptions/exception-a?org_id=org-b",
            json={"status": "RESOLVED", "resolved_by": "Test User"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 404)
        with self.session_factory() as db:
            self.assertEqual(
                db.query(OperationalException)
                .filter_by(id="exception-a")
                .one()
                .status,
                "OPEN",
            )

    def test_exception_can_be_updated_in_its_own_organization(self):
        response = self.client.patch(
            "/api/v1/exceptions/exception-a?org_id=org-a",
            json={"status": "RESOLVED", "resolved_by": "Test User"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        with self.session_factory() as db:
            updated = db.query(OperationalException).filter_by(id="exception-a").one()
            self.assertEqual(updated.status, "RESOLVED")
            self.assertEqual(updated.resolved_by, "Test User")

    def test_viewer_cannot_access_another_tenant_or_mutate_records(self):
        viewer_headers = {
            "Authorization": f"Bearer {issue_access_token('viewer-user', 0)}",
        }
        cross_tenant = self.client.get(
            "/api/v1/tenant-context/org-b",
            headers=viewer_headers,
        )
        update_rule = self.client.patch(
            "/api/v1/rules/rule-a?org_id=org-a",
            json={"severity": "CRITICAL"},
            headers=viewer_headers,
        )
        update_exception = self.client.patch(
            "/api/v1/exceptions/exception-a?org_id=org-a",
            json={"status": "RESOLVED"},
            headers=viewer_headers,
        )

        self.assertEqual(cross_tenant.status_code, 403)
        self.assertEqual(update_rule.status_code, 403)
        self.assertEqual(update_exception.status_code, 403)
        with self.session_factory() as db:
            self.assertEqual(db.query(BusinessRule).filter_by(id="rule-a").one().severity, "HIGH")
            self.assertEqual(db.query(OperationalException).filter_by(id="exception-a").one().status, "OPEN")

    def test_owner_can_create_an_organization_for_any_industry(self):
        response = self.client.post(
            "/api/v1/organizations",
            json={"name": "Northwind Health", "industry_type": "Healthcare"},
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 200)
        organization = response.json()
        self.assertEqual(organization["name"], "Northwind Health")
        self.assertEqual(organization["industry_type"], "HEALTHCARE")
        self.assertEqual(organization["base_currency"], "INR")
        with self.session_factory() as db:
            membership = db.query(OrganizationMembership).filter_by(
                user_id="test-user", org_id=organization["id"]
            ).one()
            self.assertEqual(membership.role, "owner")

    def test_viewer_cannot_create_an_organization(self):
        viewer_headers = {
            "Authorization": f"Bearer {issue_access_token('viewer-user', 0)}",
        }
        response = self.client.post(
            "/api/v1/organizations",
            json={"name": "Unauthorized Org", "industry_type": "Retail"},
            headers=viewer_headers,
        )

        self.assertEqual(response.status_code, 403)
        with self.session_factory() as db:
            self.assertIsNone(
                db.query(Organization).filter_by(name="Unauthorized Org").one_or_none()
            )

    def test_owner_can_create_user_with_immediate_username_login_and_module_scope(self):
        response = self.client.post(
            "/api/v1/organizations/org-a/users",
            json={
                "full_name": "Managed User",
                "email": "managed@example.com",
                "username": "managed.user",
                "role": "viewer",
                "password": "managed-user-password-123",
                "module_permissions": ["control"],
            },
            headers=self.headers,
        )

        self.assertEqual(response.status_code, 201, response.text)
        created = response.json()
        self.assertEqual(created["username"], "managed.user")
        self.assertEqual(created["module_permissions"], ["control"])
        with self.session_factory() as db:
            created_user = db.query(User).filter_by(id=created["user_id"]).one()
            self.assertTrue(verify_password("managed-user-password-123", created_user.password_hash))

        login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "managed.user", "password": "managed-user-password-123"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        managed_headers = {
            "Authorization": f"Bearer {issue_access_token(created['user_id'], 0)}",
        }
        profile = self.client.get("/api/v1/auth/me", headers=managed_headers)
        self.assertEqual(profile.status_code, 200, profile.text)
        self.assertEqual(profile.json()["organizations"][0]["module_permissions"], ["control"])
        self.assertEqual(
            self.client.get("/api/v1/control-tower/org-a", headers=managed_headers).status_code,
            200,
        )
        self.assertEqual(
            self.client.get("/api/v1/intelligence/org-a", headers=managed_headers).status_code,
            403,
        )

    def test_owner_can_update_module_permissions_settings_and_review_audit_log(self):
        create_user = self.client.post(
            "/api/v1/organizations/org-a/users",
            json={
                "full_name": "Access User",
                "email": "access@example.com",
                "username": "access.user",
                "role": "viewer",
                "password": "access-user-password-123",
                "module_permissions": ["control"],
            },
            headers=self.headers,
        )
        self.assertEqual(create_user.status_code, 201, create_user.text)
        user_id = create_user.json()["user_id"]

        update_access = self.client.patch(
            f"/api/v1/organizations/org-a/members/{user_id}",
            json={"module_permissions": ["control", "imports"]},
            headers=self.headers,
        )
        self.assertEqual(update_access.status_code, 200, update_access.text)
        self.assertEqual(update_access.json()["module_permissions"], ["control", "imports"])

        update_settings = self.client.put(
            "/api/v1/organizations/org-a/admin-power/settings",
            json={"settings": {
                "workspace_name": "Updated Org A",
                "default_currency": "USD",
                "timezone": "UTC",
            }},
            headers=self.headers,
        )
        self.assertEqual(update_settings.status_code, 200, update_settings.text)
        self.assertEqual(update_settings.json()["settings"]["workspace_name"], "Updated Org A")
        self.assertEqual(update_settings.json()["settings"]["default_currency"], "USD")

        audit_log = self.client.get(
            "/api/v1/organizations/org-a/admin-power/audit-logs",
            headers=self.headers,
        )
        self.assertEqual(audit_log.status_code, 200, audit_log.text)
        actions = {entry["action"] for entry in audit_log.json()}
        self.assertIn("user.created", actions)
        self.assertIn("user.access_updated", actions)
        self.assertIn("settings.updated", actions)

    def test_standard_user_cannot_access_admin_power_or_create_users(self):
        viewer_headers = {
            "Authorization": f"Bearer {issue_access_token('viewer-user', 0)}",
        }
        create_user = self.client.post(
            "/api/v1/organizations/org-a/users",
            json={
                "full_name": "Unauthorized User",
                "email": "unauthorized@example.com",
                "username": "unauthorized",
                "role": "viewer",
                "password": "unauthorized-password-123",
                "module_permissions": ["control"],
            },
            headers=viewer_headers,
        )
        update_settings = self.client.put(
            "/api/v1/organizations/org-a/admin-power/settings",
            json={"settings": {"timezone": "UTC"}},
            headers=viewer_headers,
        )
        audit_log = self.client.get(
            "/api/v1/organizations/org-a/admin-power/audit-logs",
            headers=viewer_headers,
        )

        self.assertEqual(create_user.status_code, 403)
        self.assertEqual(update_settings.status_code, 403)
        self.assertEqual(audit_log.status_code, 403)
        with self.session_factory() as db:
            self.assertIsNone(db.query(User).filter_by(username="unauthorized").one_or_none())

    def test_import_suggests_mapping_previews_and_ingests_csv(self):
        csv_content = (
            "PO Number;Plant;Supplier;Part Number;Description;Qty;Rate;Line Total;PO Date\n"
            "PO-100;Kochi;Vendor A;ITEM-1;Precision part;2;5;10;2026-06-01\n"
        )
        suggestion = self.client.post(
            "/api/v1/connectors/files/suggest-mapping",
            data={"org_id": "org-a"},
            files={"file": ("purchase-orders.csv", csv_content, "text/csv")},
            headers=self.headers,
        )

        self.assertEqual(suggestion.status_code, 200, suggestion.text)
        mapping = suggestion.json()["mapping"]
        self.assertEqual(mapping["PO Number"], "po_number")
        self.assertEqual(mapping["Plant"], "location_id")
        self.assertEqual(mapping["PO Date"], "order_date")

        upload = {
            "file": ("purchase-orders.csv", csv_content, "text/csv"),
        }
        form = {"org_id": "org-a", "mapping": json.dumps(mapping)}
        preview = self.client.post(
            "/api/v1/connectors/csv/preview",
            data=form,
            files=upload,
            headers=self.headers,
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["valid_rows"], 1)
        self.assertEqual(preview.json()["errors"], [])

        ingest = self.client.post(
            "/api/v1/connectors/csv/ingest/org-a",
            data={"mapping": json.dumps(mapping)},
            files=upload,
            headers=self.headers,
        )
        self.assertEqual(ingest.status_code, 200, ingest.text)
        self.assertEqual(ingest.json()["records_processed"], 1)
        self.assertEqual(ingest.json()["status"], "COMPLETED")
        with self.session_factory() as db:
            purchase_order = db.query(PurchaseOrder).filter_by(
                org_id="org-a", po_number="PO-100"
            ).one()
            self.assertEqual(purchase_order.location_id, "loc-a")
            self.assertEqual(
                db.query(DataImport).filter_by(org_id="org-a").count(),
                1,
            )

    def test_invalid_import_preview_is_rejected_without_partial_ingest(self):
        csv_content = (
            "PO Number,Location,Vendor,Item,Description,Quantity,Unit Price,Total,Order Date\n"
            "PO-101,Kochi,Vendor A,ITEM-1,Valid part,2,5,10,2026-06-01\n"
            "PO-102,Kochi,Vendor B,ITEM-2,Invalid part,0,5,0,2026-06-01\n"
        )
        mapping = {
            "PO Number": "po_number",
            "Location": "location_id",
            "Vendor": "vendor_name",
            "Item": "item_code",
            "Description": "item_description",
            "Quantity": "quantity",
            "Unit Price": "unit_price",
            "Total": "total_amount",
            "Order Date": "order_date",
        }
        form = {"org_id": "org-a", "mapping": json.dumps(mapping)}
        preview = self.client.post(
            "/api/v1/connectors/csv/preview",
            data=form,
            files={"file": ("purchase-orders.csv", csv_content, "text/csv")},
            headers=self.headers,
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["valid_rows"], 1)
        self.assertIn("quantity must be positive", preview.json()["errors"][0]["error"])

        ingest = self.client.post(
            "/api/v1/connectors/csv/ingest/org-a",
            data={"mapping": json.dumps(mapping)},
            files={"file": ("purchase-orders.csv", csv_content, "text/csv")},
            headers=self.headers,
        )
        self.assertEqual(ingest.status_code, 422)
        with self.session_factory() as db:
            self.assertEqual(db.query(PurchaseOrder).filter_by(org_id="org-a").count(), 0)
            self.assertEqual(db.query(DataImport).filter_by(org_id="org-a").count(), 0)

    def test_xlsx_upload_supports_suggested_mapping_and_validation(self):
        from openpyxl import Workbook

        workbook = Workbook()
        worksheet = workbook.active
        worksheet.append([
            "PO Number",
            "Plant",
            "Supplier",
            "Part Number",
            "Description",
            "Qty",
            "Rate",
            "Line Total",
            "PO Date",
        ])
        worksheet.append([
            "PO-200",
            "Kochi",
            "Vendor A",
            "ITEM-2",
            "Excel part",
            3,
            4,
            12,
            "2026-06-02",
        ])
        content = BytesIO()
        workbook.save(content)
        file_bytes = content.getvalue()

        suggestion = self.client.post(
            "/api/v1/connectors/files/suggest-mapping",
            data={"org_id": "org-a"},
            files={
                "file": (
                    "purchase-orders.xlsx",
                    file_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=self.headers,
        )
        self.assertEqual(suggestion.status_code, 200, suggestion.text)
        mapping = suggestion.json()["mapping"]
        preview = self.client.post(
            "/api/v1/connectors/csv/preview",
            data={"org_id": "org-a", "mapping": json.dumps(mapping)},
            files={
                "file": (
                    "purchase-orders.xlsx",
                    file_bytes,
                    "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                )
            },
            headers=self.headers,
        )
        self.assertEqual(preview.status_code, 200, preview.text)
        self.assertEqual(preview.json()["valid_rows"], 1)
        self.assertEqual(preview.json()["errors"], [])


if __name__ == "__main__":
    unittest.main()
