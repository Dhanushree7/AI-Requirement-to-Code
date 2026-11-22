"""
Tests for ArtifactService: schema artifact generation.
"""
import json
import pytest

from backend.app.models.project import Project, UploadedFile
from backend.app.models.requirement import ExtractedRequirement
from backend.app.models.artifact import Artifact
from backend.app.services.artifact_service import ArtifactService


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project_with_data(db, user_id=None):
    """Create a project with an uploaded file and some requirements."""
    if user_id is None:
        from tests.conftest import get_or_create_test_user
        user = get_or_create_test_user(db)
        user_id = user.id

    p = Project(name="Schema Test Project", status="idle", user_id=user_id)
    db.add(p)
    db.commit()
    db.refresh(p)

    f = UploadedFile(
        project_id=p.id,
        filename="req.txt",
        file_path="/tmp/req.txt",
        file_type="txt",
        file_size=256,
        extracted_text=(
            "Library Management System.\n"
            "FR-001 Members shall borrow books.\n"
            "ENT-001 Book entity has title, ISBN, author, available_copies.\n"
            "ENT-002 Member entity has name, email, membership_type.\n"
            "ENT-003 Borrowing entity links Member to Book with dates."
        ),
    )
    db.add(f)

    for cat, req_id, title, desc in [
        ("functional", "FR-001", "Borrow Books", "Members can borrow books"),
        ("entity", "ENT-001", "Book", "Book entity"),
        ("entity", "ENT-002", "Member", "Member entity"),
        ("entity", "ENT-003", "Borrowing", "Borrowing entity"),
    ]:
        r = ExtractedRequirement(
            project_id=p.id,
            req_id=req_id,
            category=cat,
            title=title,
            description=desc,
            priority="medium",
        )
        db.add(r)

    db.commit()
    return p


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestSchemaGeneration:
    def test_generates_schema_artifact(self, db_session):
        p = _make_project_with_data(db_session)
        artifact = ArtifactService.generate_artifact(p.id, "schema", db_session)

        assert artifact is not None
        assert artifact.artifact_type == "schema"
        assert artifact.content_json is not None

    def test_schema_content_has_tables(self, db_session):
        p = _make_project_with_data(db_session)
        artifact = ArtifactService.generate_artifact(p.id, "schema", db_session)

        content = json.loads(artifact.content_json)
        assert "tables" in content
        assert isinstance(content["tables"], list)
        assert len(content["tables"]) > 0

    def test_tables_have_required_fields(self, db_session):
        p = _make_project_with_data(db_session)
        artifact = ArtifactService.generate_artifact(p.id, "schema", db_session)

        content = json.loads(artifact.content_json)
        for table in content["tables"]:
            assert "name" in table
            assert "columns" in table

    def test_schema_saved_to_db(self, db_session):
        p = _make_project_with_data(db_session)
        ArtifactService.generate_artifact(p.id, "schema", db_session)

        saved = db_session.query(Artifact).filter_by(
            project_id=p.id, artifact_type="schema"
        ).first()
        assert saved is not None
        assert saved.status in ("done", "completed")

    def test_regenerate_updates_existing(self, db_session):
        p = _make_project_with_data(db_session)
        ArtifactService.generate_artifact(p.id, "schema", db_session)
        # Generate again — should not create duplicate
        ArtifactService.generate_artifact(p.id, "schema", db_session)

        count = db_session.query(Artifact).filter_by(
            project_id=p.id, artifact_type="schema"
        ).count()
        assert count == 1


class TestSrsGeneration:
    def test_generates_srs_artifact(self, db_session):
        p = _make_project_with_data(db_session)
        artifact = ArtifactService.generate_artifact(p.id, "srs", db_session)

        assert artifact is not None
        assert artifact.artifact_type == "srs"
        content = json.loads(artifact.content_json)
        assert "sections" in content

    def test_srs_sections_have_title_and_content(self, db_session):
        p = _make_project_with_data(db_session)
        artifact = ArtifactService.generate_artifact(p.id, "srs", db_session)
        content = json.loads(artifact.content_json)

        for section in content["sections"]:
            assert "title" in section
            assert "content" in section


class TestGenerateAll:
    def test_generates_all_six_artifacts(self, db_session):
        p = _make_project_with_data(db_session)
        result = ArtifactService.generate_all(p.id, db_session)

        artifacts = result.get("artifacts", result)
        expected = {"srs", "architecture", "schema", "api", "skeleton", "testcases"}
        assert expected.issubset(set(artifacts.keys()))

    def test_all_artifacts_status_done(self, db_session):
        p = _make_project_with_data(db_session)
        result = ArtifactService.generate_all(p.id, db_session)

        artifacts = result.get("artifacts", result)
        for art_type, status in artifacts.items():
            assert status in ("done", "completed"), f"{art_type} has status {status}"
