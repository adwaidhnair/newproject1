import os
import sys
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BACKEND_DIR)

from app.core.database import Base, get_db
from app.main import app
from app.models.erp_models import (
    BusinessRule,
    OperationalException,
    Organization,
)


class TenantUpdateTests(unittest.TestCase):
    def setUp(self):
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

    def tearDown(self):
        app.dependency_overrides.clear()
        self.engine.dispose()
        self.temp_dir.cleanup()

    def test_rule_cannot_be_updated_through_another_organizations_scope(self):
        response = self.client.patch(
            "/api/v1/rules/rule-a?org_id=org-b",
            json={"severity": "CRITICAL"},
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
        )

        self.assertEqual(response.status_code, 200)
        with self.session_factory() as db:
            updated = db.query(OperationalException).filter_by(id="exception-a").one()
            self.assertEqual(updated.status, "RESOLVED")
            self.assertEqual(updated.resolved_by, "Test User")


if __name__ == "__main__":
    unittest.main()
