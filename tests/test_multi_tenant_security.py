"""
Comprehensive test suite for Phase 1: Authentication, Authorization & Multi-Tenant Security.

Tests:
1. JWT token generation during login.
2. Token verification and payload claims.
3. Invalid credentials rejection with 401 Unauthorized.
4. Protected access without token raises 401.
5. Tampered/invalid JWT raises 401.
6. Expired JWT raises 401.
7. Query token fallback for file downloads.
8. Multi-tenant project listing isolation (User A only sees User A's projects, User B only sees User B's).
9. Cross-tenant access protection (User B cannot access, read, or download User A's projects/artifacts).
10. Non-existent project returns 404.
11. Cross-tenant requirement modification rejection (User B cannot modify User A's requirements).
12. Provider settings access control (admin only for key updates/deletion, normal user rejected with 403).
13. CORS origin security verification (no insecure wildcards).
"""

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from fastapi import HTTPException, status
from pydantic import ValidationError

from backend.app.core.config import settings
from backend.app.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    decode_access_token,
    get_current_user,
    get_current_admin_user,
    get_user_project
)
from backend.app.models.user import User
from backend.app.models.project import Project
from backend.app.models.requirement import ExtractedRequirement
from backend.app.routers.auth import login, register, LoginRequest, RegisterRequest
from backend.app.services.project_service import ProjectService
from backend.app.schemas.project import ProjectCreate, ProjectUpdate


@pytest.fixture
def user_a(db_session):
    """Create Tenant User A."""
    email = "user_a@tenant1.com"
    existing = db_session.query(User).filter(User.email == email).first()
    if existing:
        db_session.delete(existing)
        db_session.commit()

    user = User(
        full_name="Alice Engineer",
        email=email,
        hashed_password=hash_password("PasswordA123!"),
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def user_b(db_session):
    """Create Tenant User B."""
    email = "user_b@tenant2.com"
    existing = db_session.query(User).filter(User.email == email).first()
    if existing:
        db_session.delete(existing)
        db_session.commit()

    user = User(
        full_name="Bob Engineer",
        email=email,
        hashed_password=hash_password("PasswordB123!"),
        is_active=True,
        is_superuser=False
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def admin_user(db_session):
    """Create Administrator User."""
    email = "admin@platform.com"
    existing = db_session.query(User).filter(User.email == email).first()
    if existing:
        db_session.delete(existing)
        db_session.commit()

    user = User(
        full_name="Platform Admin",
        email=email,
        hashed_password=hash_password("AdminPass123!"),
        is_active=True,
        is_superuser=True
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def project_a(db_session, user_a):
    """Create a project owned by User A."""
    project = ProjectService.create_project(
        db_session,
        ProjectCreate(name="Alice Secret Project", description="Confidential requirement specs"),
        user_id=user_a.id
    )
    return project


@pytest.fixture
def project_b(db_session, user_b):
    """Create a project owned by User B."""
    project = ProjectService.create_project(
        db_session,
        ProjectCreate(name="Bob Public Project", description="Bob's workspace"),
        user_id=user_b.id
    )
    return project


class TestMultiTenantSecurity:

    def test_1_login_generates_valid_jwt(self, db_session, user_a):
        """Test login endpoint returns signed JWT access token and user info."""
        req = LoginRequest(email="user_a@tenant1.com", password="PasswordA123!")
        res = login(req, db=db_session)

        assert res["success"] is True
        assert "access_token" in res
        assert res["token_type"] == "bearer"
        assert res["user"]["id"] == user_a.id
        assert res["user"]["email"] == user_a.email
        assert res["user"]["is_superuser"] is False

        # Validate token payload
        payload = decode_access_token(res["access_token"])
        assert payload["sub"] == user_a.id
        assert payload["email"] == user_a.email
        assert "exp" in payload
        assert "iat" in payload

    def test_2_login_invalid_password_returns_401(self, db_session, user_a):
        """Test login with incorrect password returns 401 Unauthorized."""
        req = LoginRequest(email="user_a@tenant1.com", password="WrongPassword!")
        with pytest.raises(HTTPException) as exc_info:
            login(req, db=db_session)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid email or password" in exc_info.value.detail

    def test_3_login_nonexistent_email_returns_401(self, db_session):
        """Test login with unregistered email returns 401 Unauthorized."""
        req = LoginRequest(email="nobody@nowhere.com", password="Password123!")
        with pytest.raises(HTTPException) as exc_info:
            login(req, db=db_session)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_4_get_current_user_missing_token_raises_401(self, db_session):
        """Test accessing protected route without a token raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(header_token=None, query_token=None, db=db_session)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "not provided" in exc_info.value.detail

    def test_5_get_current_user_invalid_token_raises_401(self, db_session):
        """Test accessing protected route with a malformed/tampered token raises 401."""
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(header_token="invalid.malformed.token", query_token=None, db=db_session)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Invalid authentication token" in exc_info.value.detail

    def test_6_get_current_user_expired_token_raises_401(self, db_session, user_a):
        """Test accessing protected route with an expired JWT raises 401."""
        # Create an expired token (1 hour in the past)
        expired_token = create_access_token(
            {"sub": user_a.id, "email": user_a.email},
            expires_delta=timedelta(hours=-1)
        )
        with pytest.raises(HTTPException) as exc_info:
            get_current_user(header_token=expired_token, query_token=None, db=db_session)
        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "expired" in exc_info.value.detail.lower()

    def test_7_get_current_user_query_token_fallback(self, db_session, user_a):
        """Test query token parameter fallback (for direct browser file downloads)."""
        valid_token = create_access_token({"sub": user_a.id, "email": user_a.email})
        authenticated_user = get_current_user(header_token=None, query_token=valid_token, db=db_session)
        assert authenticated_user.id == user_a.id
        assert authenticated_user.email == user_a.email

    def test_8_multi_tenant_project_listing_isolation(self, db_session, user_a, user_b, project_a, project_b):
        """Test that User A only sees User A's projects, and User B only sees User B's."""
        projects_for_a = ProjectService.get_projects(db_session, user_id=user_a.id)
        project_ids_a = {p.id for p in projects_for_a}
        assert project_a.id in project_ids_a
        assert project_b.id not in project_ids_a

        projects_for_b = ProjectService.get_projects(db_session, user_id=user_b.id)
        project_ids_b = {p.id for p in projects_for_b}
        assert project_b.id in project_ids_b
        assert project_a.id not in project_ids_b

    def test_9_cross_tenant_project_access_raises_403(self, db_session, user_b, project_a):
        """Test that User B cannot access User A's project (returns 403 Forbidden)."""
        with pytest.raises(HTTPException) as exc_info:
            get_user_project(project_a.id, current_user=user_b, db=db_session)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Access denied" in exc_info.value.detail

    def test_10_owner_accesses_own_project_succeeds(self, db_session, user_a, project_a):
        """Test that User A can access their own project."""
        p = get_user_project(project_a.id, current_user=user_a, db=db_session)
        assert p.id == project_a.id
        assert p.user_id == user_a.id

    def test_11_nonexistent_project_raises_404(self, db_session, user_a):
        """Test that requesting a non-existent project raises 404 Not Found."""
        with pytest.raises(HTTPException) as exc_info:
            get_user_project("nonexistent-uuid-12345", current_user=user_a, db=db_session)
        assert exc_info.value.status_code == status.HTTP_404_NOT_FOUND

    def test_12_cross_tenant_update_and_delete_protection(self, db_session, user_b, project_a):
        """Test that User B cannot update or delete User A's project."""
        # Attempt update
        updated = ProjectService.update_project(
            db_session,
            project_a.id,
            ProjectUpdate(name="Hacked Name"),
            user_id=user_b.id
        )
        assert updated is None  # Fails to find project for User B

        # Attempt delete
        deleted = ProjectService.delete_project(
            db_session,
            project_a.id,
            user_id=user_b.id
        )
        assert deleted is False

        # Verify project A was not altered or deleted
        p = ProjectService.get_project_by_id(db_session, project_a.id)
        assert p is not None
        assert p.name == "Alice Secret Project"

    def test_13_cross_tenant_requirement_protection(self, db_session, user_a, user_b, project_a):
        """Test that User B cannot modify a requirement belonging to User A's project."""
        req = ExtractedRequirement(
            project_id=project_a.id,
            req_id="FR-001",
            title="User A Secret Requirement",
            description="Confidential details",
            category="functional",
            priority="high"
        )
        db_session.add(req)
        db_session.commit()
        db_session.refresh(req)

        # User B attempts to access User A's requirement via get_user_project on parent
        with pytest.raises(HTTPException) as exc_info:
            get_user_project(req.project_id, current_user=user_b, db=db_session)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

    def test_14_admin_authorization_enforcement(self, user_a, admin_user):
        """Test that only users with is_superuser=True can access admin endpoints."""
        # Regular user fails with 403 Forbidden
        with pytest.raises(HTTPException) as exc_info:
            get_current_admin_user(current_user=user_a)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Administrator privileges required" in exc_info.value.detail

        # Admin user succeeds
        admin = get_current_admin_user(current_user=admin_user)
        assert admin.id == admin_user.id
        assert admin.is_superuser is True

    def test_15_cors_origins_security(self):
        """Verify that CORS origins configuration does not contain insecure wildcard '*'."""
        allowed = settings.allowed_cors_origins
        assert isinstance(allowed, list)
        assert len(allowed) > 0
        assert "*" not in allowed
        for origin in allowed:
            assert origin.startswith("http://") or origin.startswith("https://")

    def test_16_zip_download_multi_tenant_and_headers(self, db_session, user_a, user_b, project_a):
        """Verify ZIP download requires project ownership and provides proper Content-Disposition."""
        from backend.app.routers.codegen import download_backend_zip
        from backend.app.models.artifact import Artifact
        import json

        # Add a mock skeleton artifact to project_a
        art = Artifact(
            project_id=project_a.id,
            artifact_type="skeleton",
            title="Backend Skeleton",
            status="completed",
            current_version=1,
            content_json=json.dumps({
                "files": [
                    {"path": "app/main.py", "content": "# FastAPI app", "language": "python"}
                ]
            })
        )
        db_session.add(art)
        db_session.commit()

        # 1. Non-owner (User B) is rejected with 403 Forbidden
        with pytest.raises(HTTPException) as exc_info:
            get_user_project(project_a.id, current_user=user_b, db=db_session)
        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN

        # 2. Owner (User A) successfully downloads ZIP with attachment header
        response = download_backend_zip(project_id=project_a.id, project=project_a, db=db_session)
        assert response.status_code == 200
        assert response.media_type == "application/zip"
        assert "Content-Disposition" in response.headers
        assert f"fastapi_starter_{project_a.id[:8]}.zip" in response.headers["Content-Disposition"]
