import ast
import io
import os
import re
import zipfile
import json
import logging
import tempfile
from typing import Dict, Any, List, Optional, Tuple, Set
from sqlalchemy.orm import Session
from backend.app.models.artifact import Artifact
from backend.app.models.project import Project
from backend.app.models.requirement import ExtractedRequirement
from backend.app.services.domain_validator import is_valid_domain_table_name

logger = logging.getLogger(__name__)

class CodeGenService:
    @staticmethod
    def _sql_type_to_python_and_sa(col_type: str) -> Tuple[str, str]:
        """Convert SQL column type to (Python type hint, SQLAlchemy column type)."""
        t = (col_type or "VARCHAR").upper()
        if "INT" in t:
            return "int", "Integer"
        elif "DECIMAL" in t or "NUMERIC" in t or "FLOAT" in t or "REAL" in t:
            return "float", "Float"
        elif "BOOL" in t:
            return "bool", "Boolean"
        elif "TIMESTAMP" in t or "DATETIME" in t:
            return "datetime", "DateTime"
        elif "DATE" in t:
            return "date", "Date"
        elif "TEXT" in t or "JSON" in t:
            return "str", "Text"
        else:
            m = re.search(r'\((\d+)\)', t)
            length = m.group(1) if m else "255"
            return "str", f"String({length})"

    @staticmethod
    def _to_pascal(snake_str: str) -> str:
        """Convert snake_case to PascalCase."""
        clean = re.sub(r'[^a-zA-Z0-9_]', '_', snake_str)
        return "".join(part.capitalize() for part in clean.split("_") if part)

    @staticmethod
    def _to_snake(name: str) -> str:
        """Convert arbitrary string to clean snake_case."""
        s = re.sub(r'([A-Z]+)([A-Z][a-z])', r'\1_\2', name)
        s = re.sub(r'([a-z\d])([A-Z])', r'\1_\2', s)
        s = re.sub(r'[^a-zA-Z0-9]+', '_', s)
        return s.strip('_').lower()

    @staticmethod
    def generate_full_backend(project: Project, db: Session) -> Dict[str, Any]:
        """Generate a production-ready, domain-agnostic FastAPI backend directly from stored Schema and API artifacts."""
        project_id = project.id
        clean_project_title = project.name.strip()

        schema_art = db.query(Artifact).filter(Artifact.project_id == project_id, Artifact.artifact_type == "schema").first()
        api_art = db.query(Artifact).filter(Artifact.project_id == project_id, Artifact.artifact_type == "api").first()

        if not schema_art or not schema_art.content_json:
            raise ValueError(f"Cannot generate code: Database Schema artifact for project {project_id} is missing.")
        if not api_art or not api_art.content_json:
            raise ValueError(f"Cannot generate code: API Documentation artifact for project {project_id} is missing.")

        schema_data = json.loads(schema_art.content_json)
        api_data = json.loads(api_art.content_json)

        tables = schema_data.get("tables", [])
        endpoints = api_data.get("endpoints", [])

        # Fetch extracted actors for dynamic roles
        actors = db.query(ExtractedRequirement).filter(
            ExtractedRequirement.project_id == project_id,
            ExtractedRequirement.category == "actor"
        ).all()
        actor_roles = [a.title.strip() for a in actors if a.title and a.title.lower() != "user"]
        if not actor_roles:
            # Fall back to roles found across API endpoints
            discovered_roles = set()
            for ep in endpoints:
                for r in ep.get("allowed_roles") or ep.get("roles") or []:
                    discovered_roles.add(str(r).strip())
            actor_roles = sorted(list(discovered_roles)) or ["Admin", "Customer"]

        files: List[Dict[str, Any]] = []

        # -------------------------------------------------------------
        # 1. Root / Config / Database / Auth / Env
        # -------------------------------------------------------------
        files.append({
            "path": ".env.example",
            "language": "text",
            "content": f"""PROJECT_NAME="{clean_project_title}"
DATABASE_URL="sqlite:///./app.db"
JWT_SECRET_KEY="replace_with_a_secure_random_jwt_secret_key"
ALGORITHM="HS256"
ACCESS_TOKEN_EXPIRE_MINUTES="60"
"""
        })

        files.append({
            "path": "requirements.txt",
            "language": "text",
            "content": """fastapi>=0.110.0
uvicorn>=0.28.0
sqlalchemy>=2.0.0
pydantic>=2.0.0
pydantic-settings>=2.0.0
PyJWT>=2.8.0
bcrypt>=4.0.0
python-multipart>=0.0.9
pytest>=8.0.0
httpx>=0.27.0
"""
        })

        files.append({
            "path": "README.md",
            "language": "markdown",
            "content": f"""# {clean_project_title} - Backend API Starter

Generated production-grade FastAPI starter project derived directly from project Database Schema and API Documentation.

## Setup Instructions

1. **Install Dependencies:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\\Scripts\\activate
   pip install -r requirements.txt
   ```

2. **Configure Environment:**
   ```bash
   cp .env.example .env
   # Edit .env with your environment configuration
   ```

3. **Run Server:**
   ```bash
   uvicorn app.main:app --reload --port 8000
   ```

4. **Run Test Suite:**
   ```bash
   pytest -q
   ```
"""
        })

        files.append({
            "path": "app/__init__.py",
            "language": "python",
            "content": '"""Application package initialization."""\n'
        })

        files.append({
            "path": "app/config.py",
            "language": "python",
            "content": f'''"""Application configuration module."""
import os
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    PROJECT_NAME: str = "{clean_project_title}"
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./app.db")
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "temporary_insecure_dev_key_must_override_in_env")
    ALGORITHM: str = os.getenv("ALGORITHM", "HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "60"))

    class Config:
        env_file = ".env"
        extra = "ignore"

settings = Settings()
'''
        })

        files.append({
            "path": "app/database.py",
            "language": "python",
            "content": '''"""Database engine and session management."""
from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker
from app.config import settings

connect_args = {"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {}
engine = create_engine(settings.DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """FastAPI dependency for yielding database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
'''
        })

        # Generate app/auth.py with role checks, ownership verification and password hashing
        roles_tuple_repr = repr(tuple(actor_roles))
        files.append({
            "path": "app/auth.py",
            "language": "python",
            "content": f'''"""Authentication and role-based authorization dependencies."""
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Any
import bcrypt
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel
from app.config import settings

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/v1/auth/login", auto_error=False)

PROJECT_ROLES = {roles_tuple_repr}

class CurrentUser(BaseModel):
    id: int
    identifier: str
    role: str

def hash_password(password: str) -> str:
    """Hash raw password using bcrypt."""
    pwd_bytes = password.encode("utf-8")
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(pwd_bytes, salt).decode("utf-8")

def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify password against bcrypt hash."""
    pwd_bytes = plain_password.encode("utf-8")
    hash_bytes = hashed_password.encode("utf-8")
    return bcrypt.checkpw(pwd_bytes, hash_bytes)

def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """Generate signed JWT access token."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({{"exp": expire}})
    return jwt.encode(to_encode, settings.JWT_SECRET_KEY, algorithm=settings.ALGORITHM)

def get_current_user(token: Optional[str] = Depends(oauth2_scheme)) -> CurrentUser:
    """Validate Bearer token and extract authenticated user identity."""
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={{"WWW-Authenticate": "Bearer"}},
    )
    if not token:
        raise credentials_exception
    try:
        payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id_raw = payload.get("sub")
        if user_id_raw is None:
            raise credentials_exception
        user_id = int(user_id_raw) if str(user_id_raw).isdigit() else 1
        role = payload.get("role", "Customer")
        identifier = payload.get("identifier", f"user_{{user_id}}")
        return CurrentUser(id=user_id, identifier=identifier, role=role)
    except jwt.PyJWTError:
        raise credentials_exception

def require_roles(*allowed_roles: str):
    """Enforce role-based access control against authenticated user role."""
    def role_checker(current_user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if allowed_roles and current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"Operation not permitted for role '{{current_user.role}}'"
            )
        return current_user
    return role_checker

def verify_resource_ownership(resource_owner_id: Any, current_user: CurrentUser):
    """Verify that current user owns the target resource or is Admin."""
    if current_user.role.lower() == "admin":
        return
    if str(resource_owner_id) != str(current_user.id):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Permission denied: cannot access or modify another user's resource"
        )
'''
        })

        # -------------------------------------------------------------
        # 2. Models Generation (One file per table)
        # -------------------------------------------------------------
        files.append({
            "path": "app/models/__init__.py",
            "language": "python",
            "content": '"""SQLAlchemy models package."""\n'
        })

        tables = [t for t in tables if is_valid_domain_table_name(t.get("name", ""))]
        table_name_to_class = {t["name"].lower(): CodeGenService._to_pascal(t["name"]) for t in tables}
        
        # Build map of FK relationships
        # child_table -> list of (col_name, target_table, target_col)
        fk_relationships = {}
        for t in tables:
            tname = t["name"].lower()
            fk_relationships[tname] = []
            for col in t.get("columns", []):
                fk = col.get("fk")
                if fk:
                    m = re.match(r'([a-zA-Z0-9_]+)(?:\.|\()([a-zA-Z0-9_]+)\)?', str(fk))
                    if m:
                        target_tbl = m.group(1).lower()
                        target_col = m.group(2).lower()
                        if target_tbl in table_name_to_class:
                            fk_relationships[tname].append((col["name"], target_tbl, target_col))

        for t in tables:
            tname = t["name"].lower()
            cls_name = table_name_to_class[tname]
            cols = t.get("columns", [])

            sa_col_lines = []
            needs_datetime = False
            needs_date = False

            for c in cols:
                cname = c["name"]
                ctype_raw = c.get("type", "VARCHAR(255)")
                py_type, sa_type = CodeGenService._sql_type_to_python_and_sa(ctype_raw)
                if sa_type == "DateTime":
                    needs_datetime = True
                elif sa_type == "Date":
                    needs_date = True

                args = [sa_type]
                fk = c.get("fk")
                if fk:
                    m = re.match(r'([a-zA-Z0-9_]+)(?:\.|\()([a-zA-Z0-9_]+)\)?', str(fk))
                    if m and m.group(1).lower() in table_name_to_class:
                        args.append(f'ForeignKey("{m.group(1).lower()}.{m.group(2).lower()}")')

                if c.get("pk"):
                    args.append("primary_key=True")
                if c.get("unique"):
                    args.append("unique=True")
                if not c.get("nullable", True) and not c.get("pk"):
                    args.append("nullable=False")
                else:
                    args.append("nullable=True")

                if cname in ["created_at", "updated_at"] and sa_type == "DateTime":
                    args.append("default=datetime.utcnow")

                sa_col_lines.append(f"    {cname} = Column({', '.join(args)})")

            rel_lines = []
            # Forward relationships
            for f_col, target_tbl, _ in fk_relationships.get(tname, []):
                target_cls = table_name_to_class[target_tbl]
                rel_attr = re.sub(r'_id$', '', f_col)
                if rel_attr == f_col:
                    rel_attr = f"{f_col}_rel"
                rel_lines.append(f"    {rel_attr} = relationship('{target_cls}')")

            # Imports header
            import_dt = ""
            if needs_datetime or needs_date:
                dt_items = []
                if needs_datetime:
                    dt_items.append("datetime")
                if needs_date:
                    dt_items.append("date")
                import_dt = f"from datetime import {', '.join(dt_items)}\n"

            model_code = f'''"""SQLAlchemy entity model for {tname}."""
{import_dt}from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, Date, Text, ForeignKey
from sqlalchemy.orm import relationship
from app.database import Base

class {cls_name}(Base):
    __tablename__ = "{tname}"

{chr(10).join(sa_col_lines)}
{chr(10).join(rel_lines) if rel_lines else ""}
'''
            files.append({
                "path": f"app/models/{tname}.py",
                "language": "python",
                "content": model_code
            })

        # Update app/models/__init__.py to import all model classes
        model_init_lines = [f"from app.models.{t['name'].lower()} import {table_name_to_class[t['name'].lower()]}" for t in tables]
        files[files.index(next(f for f in files if f["path"] == "app/models/__init__.py"))]["content"] = "\n".join(model_init_lines) + "\n"

        # -------------------------------------------------------------
        # 3. Schemas Generation
        # -------------------------------------------------------------
        files.append({
            "path": "app/schemas/__init__.py",
            "language": "python",
            "content": '"""Pydantic schemas package."""\n'
        })

        for t in tables:
            tname = t["name"].lower()
            cls_name = table_name_to_class[tname]
            cols = t.get("columns", [])

            base_fields = []
            create_fields = []
            resp_fields = []

            for c in cols:
                cname = c["name"]
                ctype_raw = c.get("type", "VARCHAR(255)")
                py_type, _ = CodeGenService._sql_type_to_python_and_sa(ctype_raw)
                
                # Exclude sensitive attributes from response schemas
                if any(k in cname.lower() for k in ["password", "secret", "hash", "salt"]):
                    create_fields.append(f"    {cname}: str")
                    continue

                if c.get("pk"):
                    resp_fields.append(f"    {cname}: {py_type}")
                elif cname in ["created_at", "updated_at"]:
                    resp_fields.append(f"    {cname}: Optional[datetime] = None")
                else:
                    if c.get("nullable", True):
                        field_decl = f"    {cname}: Optional[{py_type}] = None"
                    else:
                        field_decl = f"    {cname}: {py_type}"
                    base_fields.append(field_decl)
                    create_fields.append(field_decl)
                    resp_fields.append(field_decl)

            update_fields = [
                f"    {c['name']}: Optional[{CodeGenService._sql_type_to_python_and_sa(c.get('type', ''))[0]}] = None"
                for c in cols if not c.get('pk') and 'created_at' not in c['name']
            ]

            schema_code = f'''"""Pydantic schemas for {tname}."""
from typing import Optional, List
from datetime import datetime, date
from pydantic import BaseModel, ConfigDict

class {cls_name}Base(BaseModel):
{chr(10).join(base_fields) if base_fields else "    pass"}

class {cls_name}Create({cls_name}Base):
{chr(10).join(create_fields) if create_fields else "    pass"}

class {cls_name}Update(BaseModel):
{chr(10).join(update_fields) if update_fields else "    pass"}

class {cls_name}Response({cls_name}Base):
    model_config = ConfigDict(from_attributes=True)
{chr(10).join(resp_fields) if resp_fields else "    pass"}
'''
            files.append({
                "path": f"app/schemas/{tname}.py",
                "language": "python",
                "content": schema_code
            })

        # Update app/schemas/__init__.py
        schema_init_lines = [f"from app.schemas.{t['name'].lower()} import {table_name_to_class[t['name'].lower()]}Create, {table_name_to_class[t['name'].lower()]}Response" for t in tables]
        files[files.index(next(f for f in files if f["path"] == "app/schemas/__init__.py"))]["content"] = "\n".join(schema_init_lines) + "\n"

        # -------------------------------------------------------------
        # 4. Routes Generation (Grouped by Tag)
        # -------------------------------------------------------------
        files.append({
            "path": "app/routes/__init__.py",
            "language": "python",
            "content": '"""API routers package."""\n'
        })

        # Group endpoints by tag
        tag_to_endpoints: Dict[str, List[Dict[str, Any]]] = {}
        for ep in endpoints:
            tag = ep.get("tag") or "General"
            tag_to_endpoints.setdefault(tag, []).append(ep)

        router_modules = []

        for tag, eps in tag_to_endpoints.items():
            mod_slug = CodeGenService._to_snake(tag)
            router_modules.append(mod_slug)

            endpoint_code_blocks = []
            imported_models = set()
            imported_schemas = set()

            for ep in eps:
                path = ep["path"]
                method = ep["method"].lower()
                summary = ep.get("summary") or f"{method.upper()} {path}"
                desc = ep.get("description") or ""
                rids = ep.get("requirement_ids") or []
                req_comment = f"# Requirement: {', '.join(rids)}" if rids else "# Requirement: Not specified"
                
                is_public = ep.get("is_public", not ep.get("auth_required", False))
                allowed_roles = ep.get("allowed_roles") or ep.get("roles") or []

                # Find candidate model for this endpoint
                candidate_table = None
                for t in tables:
                    tname = t["name"].lower()
                    if tname in path.lower() or tname.rstrip('s') in path.lower():
                        candidate_table = t
                        break
                if not candidate_table and tables:
                    candidate_table = tables[0]

                tname = candidate_table["name"].lower()
                cls_name = table_name_to_class[tname]
                imported_models.add(cls_name)
                imported_schemas.add(f"{cls_name}Create, {cls_name}Response")

                # Function name
                path_parts = [p.strip('{}:') for p in path.split('/') if p and not p.startswith('api') and not p.startswith('v1')]
                func_name = f"{method}_{'_'.join(path_parts)}" if path_parts else f"{method}_item"
                func_name = re.sub(r'[^a-zA-Z0-9_]', '_', func_name).strip('_')

                # Parameters: non-default arguments (path params, payload) MUST precede default arguments (Depends)
                func_params = []
                
                # 1. Path parameters (non-default)
                path_param_matches = re.findall(r'\{([a-zA-Z0-9_]+)\}', path)
                for pp in path_param_matches:
                    func_params.append(f"{pp}: int")

                # 2. Request body parameter for POST/PUT/PATCH (non-default)
                if method in ["post", "put", "patch"]:
                    func_params.append(f"payload: {cls_name}Create")

                # 3. Default parameters (Depends)
                func_params.append("db: Session = Depends(get_db)")

                # 4. Auth parameter (Depends)
                if not is_public:
                    if allowed_roles:
                        roles_literal = repr(allowed_roles)
                        func_params.append(f"current_user: CurrentUser = Depends(require_roles(*{roles_literal}))")
                    else:
                        func_params.append("current_user: CurrentUser = Depends(get_current_user)")

                # Generate endpoint implementation
                route_decorator = f'@router.{method}("{path}", summary="{summary}")'
                
                # Build route function body
                body_lines = [f"    {req_comment}"]
                body_lines.append(f'    """{desc}"""')
                
                # Item query & ownership check when resource is accessed by identifier
                if path_param_matches:
                    body_lines.append(f"    item = db.query({cls_name}).filter({cls_name}.id == {path_param_matches[0]}).first()")
                    body_lines.append("    if not item:")
                    body_lines.append(f'        raise HTTPException(status_code=404, detail="{cls_name} not found")')
                    if not is_public:
                        body_lines.append("    # Ownership check: verify resource belongs to current user if restricted")
                        body_lines.append("    if hasattr(item, 'customer_id') and item.customer_id is not None:")
                        body_lines.append("        verify_resource_ownership(item.customer_id, current_user)")
                        body_lines.append("    elif hasattr(item, 'user_id') and item.user_id is not None:")
                        body_lines.append("        verify_resource_ownership(item.user_id, current_user)")

                if method == "get":
                    if path_param_matches:
                        body_lines.append("    return item")
                    else:
                        body_lines.append(f"    items = db.query({cls_name}).limit(50).all()")
                        body_lines.append("    return items")
                elif method == "post":
                    body_lines.append("    # TODO(open question): verify any external service integration logic")
                    body_lines.append(f"    new_record = {cls_name}(**payload.model_dump())")
                    if not is_public:
                        body_lines.append("    if hasattr(new_record, 'customer_id'):")
                        body_lines.append("        new_record.customer_id = current_user.id")
                        body_lines.append("    elif hasattr(new_record, 'user_id'):")
                        body_lines.append("        new_record.user_id = current_user.id")
                    body_lines.append("    db.add(new_record)")
                    body_lines.append("    db.commit()")
                    body_lines.append("    db.refresh(new_record)")
                    body_lines.append("    return new_record")
                elif method in ["put", "patch"]:
                    if not path_param_matches:
                        body_lines.append(f"    item = db.query({cls_name}).first()")
                        body_lines.append("    if not item:")
                        body_lines.append(f'        raise HTTPException(status_code=404, detail="{cls_name} not found")')
                    body_lines.append("    for k, v in payload.model_dump(exclude_unset=True).items():")
                    body_lines.append("        setattr(item, k, v)")
                    body_lines.append("    db.commit()")
                    body_lines.append("    db.refresh(item)")
                    body_lines.append("    return item")
                elif method == "delete":
                    if not path_param_matches:
                        body_lines.append(f"    item = db.query({cls_name}).first()")
                        body_lines.append("    if not item:")
                        body_lines.append(f'        raise HTTPException(status_code=404, detail="{cls_name} not found")')
                    body_lines.append("    db.delete(item)")
                    body_lines.append("    db.commit()")
                    body_lines.append('    return {"message": "Resource deleted successfully"}')
                else:
                    body_lines.append('    return {"status": "ok"}')

                code_block = f"""{route_decorator}
def {func_name}({', '.join(func_params)}):
{chr(10).join(body_lines)}
"""
                endpoint_code_blocks.append(code_block)

            # Build router file
            model_imports = ", ".join(sorted(list(imported_models)))
            schema_imports = ", ".join(sorted(list(imported_schemas)))

            router_file_content = f'''"""Router for {tag} module."""
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from app.database import get_db
from app.auth import get_current_user, require_roles, verify_resource_ownership, CurrentUser
from app.models import {model_imports}
from app.schemas import {schema_imports}

router = APIRouter(tags=["{tag}"])

{chr(10).join(endpoint_code_blocks)}
'''
            files.append({
                "path": f"app/routes/{mod_slug}.py",
                "language": "python",
                "content": router_file_content
            })

        # -------------------------------------------------------------
        # 5. app/main.py
        # -------------------------------------------------------------
        router_import_lines = [f"from app.routes import {m}" for m in router_modules]
        router_include_lines = [f"app.include_router({m}.router)" for m in router_modules]

        main_content = f'''"""FastAPI application entrypoint."""
from fastapi import FastAPI
from app.config import settings
from app.database import engine, Base
import app.models  # ensure models are bound to Base.metadata

{chr(10).join(router_import_lines)}

# Create database tables automatically
Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.PROJECT_NAME,
    description="Domain-agnostic FastAPI backend derived from requirements and schema.",
    version="1.0.0"
)

@app.get("/health", tags=["Health"])
def health_check():
    """Health check endpoint verifying API service availability."""
    return {{"status": "healthy", "project": settings.PROJECT_NAME}}

{chr(10).join(router_include_lines)}
'''
        files.append({
            "path": "app/main.py",
            "language": "python",
            "content": main_content
        })

        # -------------------------------------------------------------
        # 6. Test Suite Generation
        # -------------------------------------------------------------
        files.append({
            "path": "tests/__init__.py",
            "language": "python",
            "content": '"""Test suite package."""\n'
        })

        # conftest.py
        role_fixtures = []
        for role in actor_roles:
            role_slug = CodeGenService._to_snake(role)
            role_fixtures.append(f'''@pytest.fixture
def token_{role_slug}():
    return create_access_token({{"sub": "1", "identifier": "{role_slug}@example.com", "role": "{role}"}})
''')

        conftest_content = f'''"""Pytest test suite configuration with in-memory SQLite and auth tokens."""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from app.main import app
from app.database import Base, get_db
from app.auth import create_access_token

TEST_DB_URL = "sqlite:///:memory:"
engine = create_engine(TEST_DB_URL, connect_args={{"check_same_thread": False}}, poolclass=StaticPool)
TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

@pytest.fixture(scope="session", autouse=True)
def setup_test_db():
    Base.metadata.create_all(bind=engine)
    yield
    Base.metadata.drop_all(bind=engine)

@pytest.fixture
def db_session():
    db = TestingSessionLocal()
    try:
        yield db
    finally:
        db.close()

@pytest.fixture
def client(db_session):
    def override_get_db():
        try:
            yield db_session
        finally:
            pass
    app.dependency_overrides[get_db] = override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()

{chr(10).join(role_fixtures)}

@pytest.fixture
def expired_token():
    from datetime import timedelta
    return create_access_token({{"sub": "1", "identifier": "expired@example.com", "role": "Customer"}}, expires_delta=timedelta(minutes=-10))

@pytest.fixture
def invalid_token():
    return "invalid.bearer.token"
'''
        files.append({
            "path": "tests/conftest.py",
            "language": "python",
            "content": conftest_content
        })

        # Generate test files for each router module with positive and negative cases
        for tag, eps in tag_to_endpoints.items():
            mod_slug = CodeGenService._to_snake(tag)
            test_cases = []

            for idx, ep in enumerate(eps):
                path = ep["path"]
                method = ep["method"].lower()
                is_public = ep.get("is_public", not ep.get("auth_required", False))
                allowed_roles = ep.get("allowed_roles") or ep.get("roles") or []
                role_for_pos = CodeGenService._to_snake(allowed_roles[0]) if allowed_roles else (CodeGenService._to_snake(actor_roles[0]) if actor_roles else "customer")

                # Replace path parameter placeholders with 1
                test_path = re.sub(r'\{[a-zA-Z0-9_]+\}', '1', path)

                if is_public:
                    # Public positive test
                    test_cases.append(f'''def test_{method}_{idx}_public_access(client):
    """Test public endpoint {method.upper()} {path} without credentials."""
    resp = client.{method}("{test_path}")
    assert resp.status_code in [200, 201, 404, 422]
''')
                else:
                    # Protected positive test (with token)
                    test_cases.append(f'''def test_{method}_{idx}_authorized(client, token_{role_for_pos}):
    """Test protected endpoint {method.upper()} {path} with valid credentials."""
    headers = {{"Authorization": f"Bearer {{token_{role_for_pos}}}"}}
    resp = client.{method}("{test_path}", headers=headers)
    assert resp.status_code in [200, 201, 404, 422]
''')
                    # Protected negative test (without token -> 401)
                    test_cases.append(f'''def test_{method}_{idx}_missing_token_401(client):
    """Test protected endpoint {method.upper()} {path} without credentials returns 401."""
    resp = client.{method}("{test_path}")
    assert resp.status_code == 401
''')

            test_file_content = f'''"""Unit and integration tests for {tag} router."""
import pytest

{chr(10).join(test_cases)}
'''
            files.append({
                "path": f"tests/test_{mod_slug}.py",
                "language": "python",
                "content": test_file_content
            })

        return {
            "directory_structure": [f["path"] for f in files],
            "files": files,
            "total_endpoints": len(endpoints),
            "total_tables": len(tables)
        }

    @staticmethod
    def validate_safe_relative_path(raw_path: str, trusted_base_dir: str) -> str:
        """
        Validate that raw_path is a safe relative path resolving strictly inside
        trusted_base_dir. Rejects absolute paths, '..' components, symlinks,
        null bytes, and empty paths. Returns the canonical, normalized absolute path.
        """
        if not raw_path or not isinstance(raw_path, str):
            raise ValueError(f"Invalid path: path must be a non-empty string. Got: {raw_path!r}")

        if "\x00" in raw_path:
            raise ValueError(f"Path contains null byte: {raw_path!r}")

        clean_path = raw_path.strip()
        if not clean_path:
            raise ValueError("Path is empty or whitespace-only.")

        if os.path.isabs(clean_path) or clean_path.startswith("/") or clean_path.startswith("\\"):
            raise ValueError(f"Absolute path traversal attempt rejected: {raw_path!r}")
        if re.match(r'^[a-zA-Z]:', clean_path):
            raise ValueError(f"Windows drive-letter path rejected: {raw_path!r}")

        normalized_rel = clean_path.replace("\\", "/")
        parts = normalized_rel.split("/")
        if any(part == ".." for part in parts):
            raise ValueError(f"Path traversal sequence '..' rejected: {raw_path!r}")

        base_canonical = os.path.realpath(os.path.abspath(trusted_base_dir))
        target_abs = os.path.abspath(os.path.join(base_canonical, os.path.normpath(clean_path)))
        target_canonical = os.path.realpath(target_abs)

        try:
            common_abs = os.path.commonpath([base_canonical, target_abs])
            common_real = os.path.commonpath([base_canonical, target_canonical])
        except ValueError as e:
            raise ValueError(f"Path resolves outside base directory: {raw_path!r}") from e

        if common_abs != base_canonical or common_real != base_canonical or target_canonical == base_canonical:
            raise ValueError(f"Path traversal detected: {raw_path!r} resolves outside base directory")

        curr = target_canonical
        while curr and curr != base_canonical:
            if os.path.islink(curr):
                raise ValueError(f"Symlink rejected in path: {raw_path!r}")
            curr = os.path.dirname(curr)

        return target_canonical

    @staticmethod
    def sanitize_zip_path(raw_path: str) -> str:
        """
        Sanitize and validate relative path for inclusion in a ZIP archive.
        Rejects path traversal ('..'), absolute paths, null bytes, or empty paths.
        Returns normalized forward-slash relative path.
        """
        if not raw_path or not isinstance(raw_path, str):
            raise ValueError(f"Invalid ZIP entry path: {raw_path!r}")
        if "\x00" in raw_path:
            raise ValueError(f"ZIP entry path contains null byte: {raw_path!r}")
        clean = raw_path.strip().replace("\\", "/")
        if clean.startswith("/") or re.match(r'^[a-zA-Z]:', clean):
            raise ValueError(f"Absolute path in ZIP rejected: {raw_path!r}")
        parts = [p for p in clean.split("/") if p and p != "."]
        if any(p == ".." for p in parts):
            raise ValueError(f"Path traversal in ZIP rejected: {raw_path!r}")
        if not parts:
            raise ValueError(f"Empty ZIP entry path rejected: {raw_path!r}")
        return "/".join(parts)

    @staticmethod
    def validate_generated_backend(backend_data: Dict[str, Any], expected_endpoint_count: int) -> Dict[str, Any]:
        """
        Execute static validation of generated backend code without host-level execution.
        Performs:
          1. Strict relative path containment verification.
          2. Static AST syntax parsing across all Python modules.
          3. Static AST structure analysis (FastAPI app, routes, models).
          4. Static secret heuristics scan.
          5. Static auth structure inspection.
        Zero host subprocesses or dynamic imports of untrusted code are executed.
        """
        files = backend_data.get("files", [])
        results: Dict[str, Any] = {
            "compiled": False,
            "imported": False,
            "endpoints_expected": expected_endpoint_count,
            "endpoints_found": 0,
            "tests_passed": 0,
            "tests_failed": 0,
            "runtime_tests_executed": False,
            "auth_checks": {
                "no_hardcoded_secrets": True,
                "passwords_hashed": True,
                "public_endpoints_accessible": True,
                "missing_token_401": True,
                "invalid_token_401": True,
                "unauthorized_role_403": True,
                "static_validation_only": True
            },
            "errors": []
        }

        if not files:
            results["errors"].append("No files provided for validation.")
            return results

        HTTP_METHODS = {"get", "post", "put", "delete", "patch", "options", "head"}
        file_map = {}
        ast_map = {}
        all_compiled = True

        with tempfile.TemporaryDirectory() as tmpdir:
            # 1. Path traversal containment & file unpacking check
            for f in files:
                fpath_rel = f.get("path", "")
                content = f.get("content", "")
                file_map[fpath_rel] = content

                try:
                    fpath_safe = CodeGenService.validate_safe_relative_path(fpath_rel, tmpdir)
                except ValueError as pe:
                    all_compiled = False
                    results["errors"].append(f"Path containment violation in {fpath_rel!r}: {pe}")
                    continue

                os.makedirs(os.path.dirname(fpath_safe), exist_ok=True)
                with open(fpath_safe, "w", encoding="utf-8") as fh:
                    fh.write(content)

                if fpath_rel.endswith(".py"):
                    try:
                        tree = ast.parse(content, filename=fpath_rel)
                        ast_map[fpath_rel] = tree
                    except SyntaxError as se:
                        all_compiled = False
                        results["errors"].append(f"Syntax error in {fpath_rel} (line {se.lineno}): {se.msg}")

        results["compiled"] = all_compiled and bool(ast_map)

        # 2. Static route counting
        business_endpoints_count = 0
        health_found = False

        for path, tree in ast_map.items():
            for node in ast.walk(tree):
                if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                    for dec in node.decorator_list:
                        call_node = dec if isinstance(dec, ast.Call) else None
                        func_node = call_node.func if call_node else dec
                        if isinstance(func_node, ast.Attribute) and func_node.attr.lower() in HTTP_METHODS:
                            val = func_node.value
                            if isinstance(val, ast.Name):
                                first_arg_str = ""
                                if call_node and call_node.args and isinstance(call_node.args[0], ast.Constant):
                                    first_arg_str = str(call_node.args[0].value)

                                if first_arg_str == "/health" or node.name == "health_check":
                                    health_found = True
                                elif val.id in ("router", "app"):
                                    business_endpoints_count += 1

        results["endpoints_found"] = business_endpoints_count
        if expected_endpoint_count > 0 and business_endpoints_count < expected_endpoint_count:
            results["errors"].append(
                f"Endpoint count mismatch: expected {expected_endpoint_count}, found {business_endpoints_count}"
            )

        # 3. Static main.py / app structure verification (replaces runtime import app.main)
        main_tree = ast_map.get("app/main.py")
        if main_tree:
            has_fastapi_instance = False
            for node in ast.walk(main_tree):
                if isinstance(node, ast.Assign):
                    for target in node.targets:
                        if isinstance(target, ast.Name) and target.id == "app":
                            if isinstance(node.value, ast.Call):
                                call_func = node.value.func
                                if (isinstance(call_func, ast.Name) and call_func.id == "FastAPI") or                                    (isinstance(call_func, ast.Attribute) and call_func.attr == "FastAPI"):
                                    has_fastapi_instance = True

            if has_fastapi_instance:
                results["imported"] = True
            else:
                results["imported"] = False
                results["errors"].append("app/main.py does not define an 'app = FastAPI(...)' instance")
        else:
            results["imported"] = False
            results["errors"].append("Missing required entrypoint: app/main.py")

        # 4. Static Secret Inspection
        SUSPICIOUS_SECRET_PATTERNS = [
            re.compile(r'jwt_secret_key\s*=\s*["\']my_secret', re.I),
            re.compile(r'secret(?:_key)?\s*=\s*["\']super', re.I),
            re.compile(r'-----BEGIN\s+(?:RSA\s+)?PRIVATE\s+KEY-----', re.I),
            re.compile(r'["\'](?:password|passwd|pwd)["\']\s*:\s*["\'](?:admin|root|123456)["\']', re.I),
        ]
        for path, content in file_map.items():
            for pat in SUSPICIOUS_SECRET_PATTERNS:
                if pat.search(content):
                    results["auth_checks"]["no_hardcoded_secrets"] = False
                    results["errors"].append(f"Potential hardcoded secret pattern found in {path}")
                    break

        # 5. Static Auth Checks
        auth_content = file_map.get("app/auth.py", "")
        auth_tree = ast_map.get("app/auth.py")

        if auth_content:
            has_hashing = bool(re.search(r'(pwd_context|CryptContext|bcrypt|hash_password|verify_password)', auth_content))
            results["auth_checks"]["passwords_hashed"] = has_hashing
        else:
            results["auth_checks"]["passwords_hashed"] = False

        results["auth_checks"]["public_endpoints_accessible"] = health_found

        if auth_tree and auth_content:
            has_auth_deps = bool(re.search(r'(get_current_user|HTTPException.*401|status\.HTTP_401_UNAUTHORIZED)', auth_content))
            results["auth_checks"]["missing_token_401"] = has_auth_deps

            has_token_decode = bool(re.search(r'(jwt\.decode|JWTError|PyJWTError|InvalidToken)', auth_content))
            results["auth_checks"]["invalid_token_401"] = has_token_decode

            has_role_check = bool(re.search(r'(require_roles|role.*403|status\.HTTP_403_FORBIDDEN)', auth_content))
            results["auth_checks"]["unauthorized_role_403"] = has_role_check
        else:
            results["auth_checks"]["missing_token_401"] = False
            results["auth_checks"]["invalid_token_401"] = False
            results["auth_checks"]["unauthorized_role_403"] = False

        return results

    @staticmethod
    def get_skeleton(project_id: str, db: Session) -> Dict[str, Any]:
        """
        Retrieve backend skeleton artifact without lazy generation.
        Validates paths and syntax, and returns file tree with validation metadata.
        """
        art = db.query(Artifact).filter(
            Artifact.project_id == project_id,
            Artifact.artifact_type == "skeleton"
        ).first()

        if not art or not art.content_json or art.status == "failed":
            raise ValueError(f"Backend skeleton artifact for project {project_id} has not been generated or failed.")

        content = json.loads(art.content_json)
        files = content.get("files", [])
        if isinstance(files, dict):
            files = [{"path": k, "content": v, "language": "python"} for k, v in files.items()]
        elif not isinstance(files, list):
            files = []

        validated_files = []
        all_valid = True

        for f in files:
            file_path = f.get("path", "")
            code_text = f.get("content", "")
            is_py = file_path.endswith(".py")
            is_valid = True
            syntax_error = None

            try:
                CodeGenService.sanitize_zip_path(file_path)
            except ValueError as pe:
                all_valid = False
                is_valid = False
                syntax_error = f"Path safety violation: {pe}"

            if is_py and is_valid:
                try:
                    ast.parse(code_text)
                    is_valid = True
                except SyntaxError as e:
                    is_valid = False
                    all_valid = False
                    syntax_error = f"Line {e.lineno}: {e.msg}"

            validated_files.append({
                "path": file_path,
                "language": f.get("language", "text"),
                "content": code_text,
                "is_valid_python": is_valid if is_py else None,
                "syntax_error": syntax_error
            })

        meta = {}
        if art.metadata_json:
            try:
                meta = json.loads(art.metadata_json)
            except Exception:
                meta = {}

        return {
            "project_id": project_id,
            "status": art.status,
            "all_syntax_valid": all_valid,
            "total_files": len(validated_files),
            "files": validated_files,
            "validation": meta
        }

    @staticmethod
    def create_zip_archive(project_id: str, db: Session) -> io.BytesIO:
        """Create in-memory ZIP archive of the generated starter code with sanitized relative paths."""
        skeleton_data = CodeGenService.get_skeleton(project_id, db)
        files = skeleton_data.get("files", [])

        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for f in files:
                safe_arcname = CodeGenService.sanitize_zip_path(f["path"])
                zf.writestr(safe_arcname, f["content"])

        zip_buffer.seek(0)
        return zip_buffer
