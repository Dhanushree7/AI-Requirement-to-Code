"""
Shared pytest fixtures for Req-to-Code test suite.
Provides authenticated test user fixtures, database sessions, and sample projects.
"""
import os
import sys
import pytest
from pathlib import Path

# Ensure the project root is on sys.path so backend imports resolve
PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

# Use an in-memory SQLite DB for tests (never touches the real DB)
os.environ.setdefault("DATABASE_URL", "sqlite:///:memory:")
os.environ.setdefault("LLM_PROVIDER", "mock")

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool
from backend.app.core.database import Base
from backend.app.models import *  # register all models


@pytest.fixture(scope="session")
def engine():
    """Create an in-memory SQLite engine for the test session."""
    _engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(bind=_engine)
    yield _engine
    _engine.dispose()


@pytest.fixture
def db_session(engine):
    """Return a fresh database session that is rolled back after each test."""
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.rollback()
    session.close()


def get_or_create_test_user(db_session, email="testuser@example.com", full_name="Default Test User", is_superuser=False):
    """Reusable helper to create or retrieve a test user within a session."""
    from backend.app.models.user import User
    from backend.app.core.security import hash_password

    user = db_session.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            full_name=full_name,
            email=email,
            hashed_password=hash_password("TestPassword123!"),
            is_active=True,
            is_superuser=is_superuser
        )
        db_session.add(user)
        db_session.commit()
        db_session.refresh(user)
    return user


@pytest.fixture
def test_user(db_session):
    """Fixture providing a standard active test user."""
    return get_or_create_test_user(db_session)


@pytest.fixture
def admin_user(db_session):
    """Fixture providing an administrator test user."""
    return get_or_create_test_user(db_session, email="admin@example.com", full_name="Admin Test User", is_superuser=True)


@pytest.fixture
def auth_token(test_user):
    """Fixture providing a valid signed JWT access token for test_user."""
    from backend.app.core.security import create_access_token
    return create_access_token({"sub": test_user.id, "email": test_user.email})


@pytest.fixture
def auth_headers(auth_token):
    """Fixture providing Authorization headers for HTTP test calls."""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def sample_txt_path(tmp_path):
    """A small plain-text requirement document."""
    doc = tmp_path / "sample.txt"
    doc.write_text(
        "Library Management System\n\n"
        "FR-001 Users shall be able to register and log in.\n"
        "FR-002 Librarians shall add, edit and remove books.\n"
        "FR-003 Members shall borrow and return books.\n"
        "NFR-001 The system shall respond within 2 seconds.\n"
        "NFR-002 The system shall support 500 concurrent users.\n",
        encoding="utf-8",
    )
    return doc


@pytest.fixture
def sample_project(db_session, test_user):
    """Insert a minimal Project row owned by test_user and return it."""
    from backend.app.models.project import Project

    project = Project(name="Test Project", status="idle", user_id=test_user.id)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project
