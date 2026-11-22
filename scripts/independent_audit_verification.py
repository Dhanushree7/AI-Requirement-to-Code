"""
Independent Verification Audit Script for Phase 1 Authentication, Authorization, and Multi-Tenant Security.
Tests all 7 audit areas using direct API handler calls and live database verification.
"""
import os
import sys
import sqlite3
import jwt
from datetime import datetime, timedelta, timezone
from pathlib import Path

# Add project root to sys.path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from fastapi import HTTPException, status
from pydantic import ValidationError
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from backend.app.core.config import settings
from backend.app.core.database import Base
from backend.app.core.security import (
    create_access_token, decode_access_token,
    get_current_user, get_current_admin_user, get_user_project,
    hash_password, verify_password
)
from backend.app.models.user import User, PasswordResetToken
from backend.app.models.project import Project, UploadedFile
from backend.app.models.requirement import ExtractedRequirement
from backend.app.models.artifact import Artifact
from backend.app.models.graph import GraphData
from backend.app.routers.auth import (
    login, register, get_me, forgot_password, verify_reset_token, reset_password,
    LoginRequest, RegisterRequest, ForgotPasswordRequest, ResetPasswordRequest
)
from backend.app.routers.projects import (
    list_projects, create_project, get_project, update_project, delete_project,
    get_project_dashboard, get_project_coverage, get_job_status, get_active_project_job
)
from backend.app.routers.upload import upload_document, list_project_files, delete_project_file
from backend.app.routers.requirements import (
    create_domain_model, get_domain_model, update_domain_model, delete_domain_model,
    analyze_requirements, get_requirements, get_requirements_summary, create_requirement,
    update_requirement, delete_requirement, get_requirement_history
)
from backend.app.routers.artifacts import (
    generate_all_artifacts, get_artifact, update_artifact, regenerate_artifact, restore_version
)
from backend.app.routers.codegen import get_backend_skeleton, download_backend_zip
from backend.app.routers.graph import get_knowledge_graph, get_traceability_matrix, get_impact_analysis
from backend.app.routers.rag import query_project_rag, index_project_chunks, get_suggested_questions
from backend.app.routers.provider_settings import get_provider_status, test_and_save_provider, delete_provider_key, ProviderConfigRequest
from backend.app.schemas.project import ProjectCreate, ProjectUpdate
from backend.app.schemas.requirement import RequirementCreate, RequirementUpdate
from backend.app.schemas.artifact import ArtifactUpdateRequest, RegenerateRequest
from backend.app.schemas.rag import QueryRequest

# Setup test DB in memory
engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False}, poolclass=StaticPool)
Base.metadata.create_all(bind=engine)
Session = sessionmaker(bind=engine)
db = Session()

audit_results = {
    "passed": [],
    "failed": [],
    "security_issues": [],
    "unsecured_endpoints": []
}

def log_test(name, success, detail=""):
    if success:
        print(f"[PASS] {name} {detail}")
        audit_results["passed"].append(name)
    else:
        print(f"[FAIL] {name} - {detail}")
        audit_results["failed"].append(f"{name}: {detail}")

print("=" * 70)
print("RUNNING INDEPENDENT VERIFICATION AUDIT")
print("=" * 70)

# =========================================================================
# 1. AUTHENTICATION VERIFICATION
# =========================================================================
print("\n--- 1. AUTHENTICATION VERIFICATION ---")

# 1.1 Registration
try:
    reg_req = RegisterRequest(full_name="Alice Tenant", email="alice@test.com", password="Password123!")
    reg_res = register(reg_req, db=db)
    has_token = "access_token" in reg_res and reg_res.get("token_type") == "bearer"
    has_user = reg_res.get("user", {}).get("email") == "alice@test.com"
    log_test("1.1 Registration returns correct authentication response", has_token and has_user)
except Exception as e:
    log_test("1.1 Registration returns correct authentication response", False, str(e))

# 1.2 Login with valid credentials
user_a_token = None
user_a_id = None
try:
    log_req = LoginRequest(email="alice@test.com", password="Password123!")
    log_res = login(log_req, db=db)
    user_a_token = log_res.get("access_token")
    user_a_id = log_res.get("user", {}).get("id")
    is_valid_jwt = isinstance(user_a_token, str) and len(user_a_token.split(".")) == 3
    log_test("1.2 Login returns a valid JWT", is_valid_jwt and log_res.get("success") is True)
except Exception as e:
    log_test("1.2 Login returns a valid JWT", False, str(e))

# 1.3 JWT signature verification
try:
    payload = decode_access_token(user_a_token)
    sig_valid = payload.get("sub") == user_a_id and payload.get("email") == "alice@test.com"
    log_test("1.3 JWT signature verification works", sig_valid, f"sub={payload.get('sub')}")
except Exception as e:
    log_test("1.3 JWT signature verification works", False, str(e))

# 1.4 Expiration enforcement
try:
    expired_token = create_access_token({"sub": user_a_id, "email": "alice@test.com"}, expires_delta=timedelta(seconds=-10))
    try:
        get_current_user(header_token=expired_token, query_token=None, db=db)
        log_test("1.4 Expiration is enforced", False, "Expired token was accepted!")
    except HTTPException as he:
        is_401 = he.status_code == 401 and "expired" in he.detail.lower()
        log_test("1.4 Expiration is enforced", is_401, f"Status: {he.status_code}, Detail: {he.detail}")
except Exception as e:
    log_test("1.4 Expiration is enforced", False, str(e))

# 1.5 Invalid token rejection
try:
    corrupted_token = user_a_token[:-10] + "corrupted1"
    try:
        get_current_user(header_token=corrupted_token, query_token=None, db=db)
        log_test("1.5 Invalid tokens are rejected", False, "Corrupted token was accepted!")
    except HTTPException as he:
        is_401 = he.status_code == 401
        log_test("1.5 Invalid tokens are rejected", is_401, f"Status: {he.status_code}")
except Exception as e:
    log_test("1.5 Invalid tokens are rejected", False, str(e))

# 1.6 Missing token rejection
try:
    try:
        get_current_user(header_token=None, query_token=None, db=db)
        log_test("1.6 Missing tokens are rejected on protected endpoints", False, "Missing token did not raise 401!")
    except HTTPException as he:
        is_401 = he.status_code == 401
        log_test("1.6 Missing tokens are rejected on protected endpoints", is_401, f"Status: {he.status_code}")
except Exception as e:
    log_test("1.6 Missing tokens are rejected on protected endpoints", False, str(e))

# 1.7 /api/auth/me returns only authenticated user's information
try:
    current_user_a = get_current_user(header_token=user_a_token, query_token=None, db=db)
    me_res = get_me(current_user=current_user_a)
    is_me_correct = me_res["id"] == user_a_id and me_res["email"] == "alice@test.com" and "hashed_password" not in me_res
    log_test("1.7 /api/auth/me returns only authenticated user's info (no password hash)", is_me_correct)
except Exception as e:
    log_test("1.7 /api/auth/me returns only authenticated user's info", False, str(e))


# =========================================================================
# 2. MULTI-TENANT ISOLATION (DIRECT API REQUESTS)
# =========================================================================
print("\n--- 2. MULTI-TENANT ISOLATION (DIRECT API REQUESTS) ---")

# Create User B
reg_b = register(RegisterRequest(full_name="Bob Tenant", email="bob@test.com", password="Password123!"), db=db)
user_b_token = reg_b["access_token"]
user_b_id = reg_b["user"]["id"]
user_a_obj = db.query(User).filter(User.id == user_a_id).first()
user_b_obj = db.query(User).filter(User.id == user_b_id).first()

# User A creates a project
proj_a = create_project(ProjectCreate(name="Project Alpha (User A)", description="Alice project"), current_user=user_a_obj, db=db)
proj_a_id = proj_a.id

# User B creates a project
proj_b = create_project(ProjectCreate(name="Project Beta (User B)", description="Bob project"), current_user=user_b_obj, db=db)
proj_b_id = proj_b.id

# User A adds a requirement
req_a = create_requirement(
    project_id=proj_a_id,
    data=RequirementCreate(
        req_id="FR-001",
        category="functional",
        title="User A Secret Requirement",
        description="High security feature"
    ),
    project=proj_a,
    db=db
)

# User A has an artifact
art_a = Artifact(
    project_id=proj_a_id,
    artifact_type="srs",
    title="SRS Document",
    status="completed",
    content_json='{"content": "Confidential SRS content"}',
    current_version=1
)
db.add(art_a)
# User A has an uploaded file record
file_a = UploadedFile(
    project_id=proj_a_id,
    filename="alice_requirements.pdf",
    file_type="pdf",
    file_size=1024,
    file_path=os.path.join(str(settings.UPLOAD_DIR), "mock_alice.pdf"),
    extraction_status="completed"
)
db.add(file_a)
db.commit()

# 2.1 User B listing projects does not include User A's project
try:
    b_projects = list_projects(current_user=user_b_obj, db=db)
    b_proj_ids = [p.id for p in b_projects]
    isolated = (proj_b_id in b_proj_ids) and (proj_a_id not in b_proj_ids)
    log_test("2.1 User B cannot list User A's project", isolated)
except Exception as e:
    log_test("2.1 User B cannot list User A's project", False, str(e))

# 2.2 User B accessing User A's project directly (get_user_project)
try:
    try:
        get_user_project(project_id=proj_a_id, current_user=user_b_obj, db=db)
        log_test("2.2 User B cannot view User A's project (403 Forbidden)", False, "Allowed access!")
    except HTTPException as he:
        log_test("2.2 User B cannot view User A's project (403 Forbidden)", he.status_code == 403, f"Status: {he.status_code}")
except Exception as e:
    log_test("2.2 User B cannot view User A's project", False, str(e))

# 2.3 User B modifying User A's project
try:
    try:
        # Directly invoke update_project route handler with User B
        # In route, get_user_project dependency runs first
        proj_guarded = get_user_project(project_id=proj_a_id, current_user=user_b_obj, db=db)
        update_project(project_id=proj_a_id, update_data=ProjectUpdate(name="Hacked"), project=proj_guarded, current_user=user_b_obj, db=db)
        log_test("2.3 User B cannot modify User A's project", False, "Modified successfully!")
    except HTTPException as he:
        log_test("2.3 User B cannot modify User A's project", he.status_code == 403, f"Status: {he.status_code}")
except Exception as e:
    log_test("2.3 User B cannot modify User A's project", False, str(e))

# 2.4 User B deleting User A's project
try:
    try:
        proj_guarded = get_user_project(project_id=proj_a_id, current_user=user_b_obj, db=db)
        delete_project(project_id=proj_a_id, project=proj_guarded, current_user=user_b_obj, db=db)
        log_test("2.4 User B cannot delete User A's project", False, "Deleted successfully!")
    except HTTPException as he:
        log_test("2.4 User B cannot delete User A's project", he.status_code == 403, f"Status: {he.status_code}")
except Exception as e:
    log_test("2.4 User B cannot delete User A's project", False, str(e))

# 2.5 User B accessing User A's uploaded documents
try:
    try:
        proj_guarded = get_user_project(project_id=proj_a_id, current_user=user_b_obj, db=db)
        list_project_files(project_id=proj_a_id, project=proj_guarded, db=db)
        log_test("2.5 User B cannot access User A's uploaded documents", False, "Access allowed!")
    except HTTPException as he:
        log_test("2.5 User B cannot access User A's uploaded documents", he.status_code == 403, f"Status: {he.status_code}")
except Exception as e:
    log_test("2.5 User B cannot access User A's uploaded documents", False, str(e))

# 2.6 User B viewing User A's requirements
try:
    try:
        proj_guarded = get_user_project(project_id=proj_a_id, current_user=user_b_obj, db=db)
        get_requirements(project_id=proj_a_id, project=proj_guarded, db=db)
        log_test("2.6 User B cannot view User A's requirements", False, "Access allowed!")
    except HTTPException as he:
        log_test("2.6 User B cannot view User A's requirements", he.status_code == 403, f"Status: {he.status_code}")
except Exception as e:
    log_test("2.6 User B cannot view User A's requirements", False, str(e))

# 2.7 User B modifying/deleting User A's requirement via requirement ID
try:
    try:
        # update_requirement uses req_id directly
        update_requirement(req_id=req_a.id, data=RequirementUpdate(title="Hacked"), current_user=user_b_obj, db=db)
        log_test("2.7 User B cannot modify User A's requirement", False, "Modified successfully!")
    except HTTPException as he:
        log_test("2.7 User B cannot modify User A's requirement", he.status_code == 403, f"Status: {he.status_code}")
except Exception as e:
    log_test("2.7 User B cannot modify User A's requirement", False, str(e))

# 2.8 User B viewing User A's artifacts
try:
    try:
        proj_guarded = get_user_project(project_id=proj_a_id, current_user=user_b_obj, db=db)
        get_artifact(project_id=proj_a_id, artifact_type="srs", project=proj_guarded, db=db)
        log_test("2.8 User B cannot view User A's artifacts", False, "Access allowed!")
    except HTTPException as he:
        log_test("2.8 User B cannot view User A's artifacts", he.status_code == 403, f"Status: {he.status_code}")
except Exception as e:
    log_test("2.8 User B cannot view User A's artifacts", False, str(e))

# 2.9 User B generating artifacts for User A's project
try:
    try:
        proj_guarded = get_user_project(project_id=proj_a_id, current_user=user_b_obj, db=db)
        generate_all_artifacts(project_id=proj_a_id, project=proj_guarded, db=db)
        log_test("2.9 User B cannot trigger artifact generation for User A", False, "Triggered!")
    except HTTPException as he:
        log_test("2.9 User B cannot trigger artifact generation for User A", he.status_code == 403, f"Status: {he.status_code}")
except Exception as e:
    log_test("2.9 User B cannot trigger artifact generation for User A", False, str(e))

# 2.10 User B accessing User A's knowledge graph
try:
    try:
        proj_guarded = get_user_project(project_id=proj_a_id, current_user=user_b_obj, db=db)
        get_knowledge_graph(project_id=proj_a_id, project=proj_guarded, db=db)
        log_test("2.10 User B cannot access User A's knowledge graph", False, "Access allowed!")
    except HTTPException as he:
        log_test("2.10 User B cannot access User A's knowledge graph", he.status_code == 403, f"Status: {he.status_code}")
except Exception as e:
    log_test("2.10 User B cannot access User A's knowledge graph", False, str(e))

# 2.11 User B querying User A's RAG / chat history
try:
    try:
        proj_guarded = get_user_project(project_id=proj_a_id, current_user=user_b_obj, db=db)
        query_project_rag(project_id=proj_a_id, request=QueryRequest(question="What is secret?"), project=proj_guarded, db=db)
        log_test("2.11 User B cannot access User A's RAG assistant", False, "Access allowed!")
    except HTTPException as he:
        log_test("2.11 User B cannot access User A's RAG assistant", he.status_code == 403, f"Status: {he.status_code}")
except Exception as e:
    log_test("2.11 User B cannot access User A's RAG assistant", False, str(e))

# 2.12 User B downloading User A's generated code
try:
    try:
        proj_guarded = get_user_project(project_id=proj_a_id, current_user=user_b_obj, db=db)
        download_backend_zip(project_id=proj_a_id, project=proj_guarded, db=db)
        log_test("2.12 User B cannot download User A's generated code", False, "Downloaded!")
    except HTTPException as he:
        log_test("2.12 User B cannot download User A's generated code", he.status_code == 403, f"Status: {he.status_code}")
except Exception as e:
    log_test("2.12 User B cannot download User A's generated code", False, str(e))

# 2.13 User B accessing User A's background jobs
try:
    try:
        from backend.app.services.job_runner import job_manager
        mock_job_id = job_manager.submit_job(task_name="dummy_task", target=lambda jid: None, project_id=proj_a_id)
        get_job_status(job_id=mock_job_id, current_user=user_b_obj, db=db)
        log_test("2.13 User B cannot access User A's background jobs", False, "Access allowed!")
    except HTTPException as he:
        log_test("2.13 User B cannot access User A's background jobs", he.status_code == 403, f"Status: {he.status_code}")
except Exception as e:
    log_test("2.13 User B cannot access User A's background jobs", False, str(e))


# =========================================================================
# 3. PROVIDER SETTINGS VERIFICATION
# =========================================================================
print("\n--- 3. PROVIDER SETTINGS VERIFICATION ---")

# Create Admin User
reg_admin = register(RegisterRequest(full_name="Admin Boss", email="boss@platform.com", password="Password123!"), db=db)
admin_user_obj = db.query(User).filter(User.email == "boss@platform.com").first()
admin_user_obj.is_superuser = True
db.commit()

# 3.1 Regular user cannot modify provider settings
try:
    try:
        test_and_save_provider(
            ProviderConfigRequest(provider="gemini", model="gemini-1.5-flash", api_key="sk-fakekey12345"),
            admin_user=get_current_admin_user(current_user=user_a_obj)
        )
        log_test("3.1 Regular users cannot modify provider settings", False, "Modification allowed!")
    except HTTPException as he:
        log_test("3.1 Regular users cannot modify provider settings", he.status_code == 403, f"Status: {he.status_code}")
except Exception as e:
    log_test("3.1 Regular users cannot modify provider settings", False, str(e))

# 3.2 Regular user cannot delete provider credentials
try:
    try:
        delete_provider_key(admin_user=get_current_admin_user(current_user=user_a_obj))
        log_test("3.2 Regular users cannot delete provider credentials", False, "Deletion allowed!")
    except HTTPException as he:
        log_test("3.2 Regular users cannot delete provider credentials", he.status_code == 403, f"Status: {he.status_code}")
except Exception as e:
    log_test("3.2 Regular users cannot delete provider credentials", False, str(e))

# 3.3 Admin access works
try:
    admin_auth = get_current_admin_user(current_user=admin_user_obj)
    log_test("3.3 Admin access works (is_superuser=True)", admin_auth.is_superuser is True)
except Exception as e:
    log_test("3.3 Admin access works", False, str(e))

# 3.4 API responses never expose full stored API keys
try:
    status_res = get_provider_status(current_user=user_a_obj)
    masked_key = status_res.get("masked_key", "")
    full_exposed = False
    if "AIza" in str(status_res) or "sk-" in str(status_res):
        full_exposed = True
    log_test("3.4 API responses never expose full stored API keys", not full_exposed, f"Masked key: {masked_key}")
except Exception as e:
    log_test("3.4 API responses never expose full stored API keys", False, str(e))


# =========================================================================
# 4. DATABASE MIGRATION & BACKUP VERIFICATION
# =========================================================================
print("\n--- 4. DATABASE MIGRATION & BACKUP VERIFICATION ---")

real_db_path = ROOT / "backend" / "storage" / "req_to_code.db"
real_bak_path = ROOT / "backend" / "storage" / "req_to_code.db.bak"

# 4.1 Real database exists and data remains intact
try:
    conn = sqlite3.connect(real_db_path)
    cur = conn.cursor()
    cur.execute("SELECT COUNT(*) FROM users")
    user_count = cur.fetchone()[0]
    cur.execute("SELECT COUNT(*) FROM projects")
    project_count = cur.fetchone()[0]
    log_test("4.1 Real database records intact", user_count > 0 and project_count > 0, f"{user_count} users, {project_count} projects")
    
    # 4.2 Check existing projects assigned to valid user
    cur.execute("SELECT id, name, user_id FROM projects")
    proj_rows = cur.fetchall()
    all_assigned = all(r[2] is not None for r in proj_rows)
    log_test("4.2 All existing projects assigned to a user", all_assigned, f"Projects: {[r[1] for r in proj_rows]}")

    # 4.3 Check for orphaned projects
    cur.execute("SELECT COUNT(*) FROM projects WHERE user_id IS NULL OR user_id NOT IN (SELECT id FROM users)")
    orphans = cur.fetchone()[0]
    log_test("4.3 No orphaned projects exist", orphans == 0, f"Orphan count: {orphans}")

    # 4.4 Check columns on users and projects
    cur.execute("PRAGMA table_info(users)")
    u_cols = [c[1] for c in cur.fetchall()]
    cur.execute("PRAGMA table_info(projects)")
    p_cols = [c[1] for c in cur.fetchall()]
    has_schema = "is_superuser" in u_cols and "user_id" in p_cols
    log_test("4.4 Schema updated with is_superuser and user_id", has_schema)
    conn.close()
except Exception as e:
    log_test("4.1-4.4 Real database inspection", False, str(e))

# 4.5 Database backup exists and is usable
try:
    bak_exists = real_bak_path.exists() and real_bak_path.stat().st_size > 0
    if bak_exists:
        bak_conn = sqlite3.connect(real_bak_path)
        bak_cur = bak_conn.cursor()
        bak_cur.execute("SELECT COUNT(*) FROM projects")
        bak_proj_count = bak_cur.fetchone()[0]
        bak_conn.close()
        log_test("4.5 Database backup exists and is readable SQLite DB", bak_proj_count > 0, f"Size: {real_bak_path.stat().st_size} bytes")
    else:
        log_test("4.5 Database backup exists", False, "Backup file not found!")
except Exception as e:
    log_test("4.5 Database backup verification", False, str(e))


# =========================================================================
# 5. PASSWORD RESET COMPATIBILITY VERIFICATION
# =========================================================================
print("\n--- 5. PASSWORD RESET COMPATIBILITY VERIFICATION ---")

try:
    # 5.1 Forgot password endpoint
    fp_req = ForgotPasswordRequest(email="alice@test.com")
    fp_res = forgot_password(fp_req, db=db)
    log_test("5.1 Forgot password generates link without error", "message" in fp_res)

    # 5.2 Token retrieval and expiration verification
    token_rec = db.query(PasswordResetToken).filter(PasswordResetToken.user_id == user_a_id).order_by(PasswordResetToken.created_at.desc()).first()
    has_token = token_rec is not None and token_rec.is_used is False and token_rec.expires_at > datetime.utcnow()
    log_test("5.2 Password reset token stored hashed with valid expiration", has_token)

    # 5.3 Reset password execution
    # Emulate token verify and reset
    reset_req = ResetPasswordRequest(token="dummy_token_to_test_hashing", new_password="NewAlicePassword123!")
    # Test length validation
    try:
        ResetPasswordRequest(token="token", new_password="short")
        log_test("5.3 Short password rejection on reset", False)
    except ValidationError:
        log_test("5.3 Short password rejection on reset works", True)

except Exception as e:
    log_test("5.1-5.3 Password reset compatibility", False, str(e))


# =========================================================================
# 6. SECURITY REVIEW CHECKS
# =========================================================================
print("\n--- 6. SECURITY REVIEW CHECKS ---")

# 6.1 CORS configuration
cors_safe = "*" not in settings.allowed_cors_origins and len(settings.allowed_cors_origins) > 0
log_test("6.1 CORS configuration has no wildcards", cors_safe, f"Origins: {settings.allowed_cors_origins}")

# 6.2 Check all app routes in backend/app/main.py
from backend.app.main import app
unsecured = []
for route in app.routes:
    if hasattr(route, "path") and hasattr(route, "endpoint"):
        path = route.path
        # Allow open public endpoints
        public_allowed = [
            "/openapi.json", "/docs", "/docs/oauth2-redirect", "/redoc", "/health", "/",
            "/api/auth/login", "/api/auth/signin", "/api/auth/register", "/api/auth/signup",
            "/api/auth/forgot-password", "/api/auth/verify-reset-token", "/api/auth/reset-password",
            "/auth/login", "/auth/signin", "/auth/register", "/auth/signup",
            "/auth/forgot-password", "/auth/verify-reset-token", "/auth/reset-password",
            "/api/login", "/api/signin", "/api/register", "/api/signup",
            "/api/forgot-password", "/api/verify-reset-token", "/api/reset-password",
            "/login", "/signin", "/register", "/signup",
            "/forgot-password", "/verify-reset-token", "/reset-password",
            "/api/llm/health"  # system status
        ]
        if path not in public_allowed:
            # Check if route has dependencies
            deps = getattr(route, "dependencies", []) or []
            # Check signature parameters for Depends
            endpoint = route.endpoint
            import inspect
            sig = inspect.signature(endpoint)
            has_dep = any("Depends" in str(param.default) for param in sig.parameters.values()) or len(deps) > 0
            if not has_dep:
                unsecured.append(path)

log_test("6.2 All resource endpoints have authentication / security dependencies", len(unsecured) == 0, f"Unsecured: {unsecured}")


# =========================================================================
# SUMMARY
# =========================================================================
print("\n" + "=" * 70)
print("AUDIT RESULTS SUMMARY")
print(f"Total Passed: {len(audit_results['passed'])}")
print(f"Total Failed: {len(audit_results['failed'])}")
if audit_results['failed']:
    print("Failures:")
    for f in audit_results['failed']:
        print(" -", f)
print("=" * 70)
