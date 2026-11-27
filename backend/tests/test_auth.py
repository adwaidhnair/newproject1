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
from app.models.erp_models import Organization


class AuthenticationTests(unittest.TestCase):
    def setUp(self):
        self.environment = patch.dict(
            os.environ,
            {
                "ENVIRONMENT": "development",
                "ERP_API_KEY": "",
                "AUTH_TOKEN_SECRET": "auth-tests-secret-with-enough-entropy-for-tests",
                "BOOTSTRAP_SETUP_TOKEN": "first-owner-test-token-with-at-least-32-bytes",
                "LOGIN_RATE_MAX_ATTEMPTS": "10",
            },
        )
        self.environment.start()
        self.temporary_directory = tempfile.TemporaryDirectory()
        self.engine = create_engine(
            f"sqlite:///{os.path.join(self.temporary_directory.name, 'auth.db')}",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        self.session_factory = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        with self.session_factory() as db:
            db.add_all(
                [
                    Organization(id="org-a", name="Org A", industry_type="FMCG"),
                    Organization(id="org-b", name="Org B", industry_type="MANUFACTURING"),
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
        self.environment.stop()
        self.engine.dispose()
        self.temporary_directory.cleanup()

    def register_owner(self, email="owner@example.com", username="owner"):
        return self.client.post(
            "/api/v1/auth/register",
            json={
                "email": email,
                "username": username,
                "password": "test-password-123",
                "full_name": "Test Owner",
                "organization_id": "org-a",
                "setup_token": "first-owner-test-token-with-at-least-32-bytes",
            },
        )

    def test_private_api_rejects_anonymous_requests(self):
        response = self.client.get("/api/v1/bootstrap")
        self.assertEqual(response.status_code, 401)

    def test_first_owner_can_be_claimed_once_and_scoped_to_one_tenant(self):
        response = self.register_owner()
        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(self.client.get("/api/v1/tenant-context/org-a").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/tenant-context/org-b").status_code, 403)

        second_claim = self.register_owner("second@example.com")
        self.assertEqual(second_claim.status_code, 403)

    def test_login_logout_revokes_the_cookie_and_login_restores_access(self):
        self.assertEqual(self.register_owner().status_code, 200)
        self.assertEqual(self.client.get("/api/v1/bootstrap").status_code, 200)

        logout = self.client.post(
            "/api/v1/auth/logout",
            headers={"Origin": "http://localhost:5173"},
        )
        self.assertEqual(logout.status_code, 200, logout.text)
        self.assertEqual(self.client.get("/api/v1/bootstrap").status_code, 401)

        login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "OWNER", "password": "test-password-123"},
        )
        self.assertEqual(login.status_code, 200, login.text)
        self.assertEqual(self.client.get("/api/v1/bootstrap").status_code, 200)

    def test_user_can_change_password_and_old_password_stops_working(self):
        self.assertEqual(self.register_owner().status_code, 200)

        change = self.client.post(
            "/api/v1/auth/change-password",
            json={
                "current_password": "test-password-123",
                "new_password": "a-new-strong-password-456",
            },
            headers={"Origin": "http://localhost:5173"},
        )
        self.assertEqual(change.status_code, 200, change.text)
        self.assertTrue(change.json()["password_changed"])
        self.assertEqual(self.client.get("/api/v1/auth/me").status_code, 200)

        self.client.post(
            "/api/v1/auth/logout",
            headers={"Origin": "http://localhost:5173"},
        )
        old_password_login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "owner", "password": "test-password-123"},
        )
        self.assertEqual(old_password_login.status_code, 401)

        new_password_login = self.client.post(
            "/api/v1/auth/login",
            json={"username": "owner", "password": "a-new-strong-password-456"},
        )
        self.assertEqual(new_password_login.status_code, 200, new_password_login.text)

    def test_invitation_creates_a_tenant_scoped_member(self):
        self.assertEqual(self.register_owner().status_code, 200)
        invitation_response = self.client.post(
            "/api/v1/organizations/org-a/invitations",
            json={"email": "analyst@example.com", "role": "analyst"},
            headers={"Origin": "http://localhost:5173"},
        )
        self.assertEqual(invitation_response.status_code, 200, invitation_response.text)
        token = invitation_response.json()["invitation_token"]
        self.assertEqual(self.client.get(f"/api/v1/auth/invitations/{token}").status_code, 200)

        accepted = self.client.post(
            "/api/v1/auth/accept-invitation",
            json={
                "token": token,
                "full_name": "Test Analyst",
                "username": "test.analyst",
                "password": "analyst-password-123",
            },
            headers={"Origin": "http://localhost:5173"},
        )
        self.assertEqual(accepted.status_code, 200, accepted.text)
        membership = self.client.get("/api/v1/auth/me")
        self.assertEqual(membership.status_code, 200, membership.text)
        self.assertEqual(membership.json()["organizations"][0]["role"], "analyst")
        self.assertEqual(self.client.get("/api/v1/tenant-context/org-a").status_code, 200)
        self.assertEqual(self.client.get("/api/v1/tenant-context/org-b").status_code, 403)

    def test_cookie_authenticated_writes_require_a_trusted_origin(self):
        self.assertEqual(self.register_owner().status_code, 200)
        payload = {"name": "Untrusted organization", "industry_type": "FMCG"}

        missing_origin = self.client.post("/api/v1/organizations", json=payload)
        untrusted_origin = self.client.post(
            "/api/v1/organizations",
            json=payload,
            headers={"Origin": "https://attacker.example"},
        )

        self.assertEqual(missing_origin.status_code, 403)
        self.assertEqual(untrusted_origin.status_code, 403)


if __name__ == "__main__":
    unittest.main()
