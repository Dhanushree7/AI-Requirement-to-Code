"""
Tests for RequirementService: extraction pipeline with MockProvider,
CRUD operations, and summary calculation.
"""
import pytest
from unittest.mock import patch, MagicMock

from backend.app.models.project import Project, UploadedFile
from backend.app.models.requirement import ExtractedRequirement
from backend.app.schemas.requirement import RequirementCreate, RequirementUpdate
from backend.app.services.requirement_service import RequirementService
from tests.conftest import get_or_create_test_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(db, name="Library System"):
    user = get_or_create_test_user(db)
    p = Project(name=name, status="idle", user_id=user.id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _make_file(db, project_id, text="FR-001 Users shall log in.\nNFR-001 System must be fast."):
    f = UploadedFile(
        project_id=project_id,
        filename="sample.txt",
        file_path="/tmp/sample.txt",
        file_type="txt",
        file_size=len(text.encode("utf-8")),
        extracted_text=text,
    )
    db.add(f)
    db.commit()
    db.refresh(f)
    return f


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestAnalyzeProjectRequirements:
    def test_raises_if_project_not_found(self, db_session):
        with pytest.raises(ValueError, match="Project not found"):
            RequirementService.analyze_project_requirements("nonexistent-id", db_session)

    def test_raises_if_no_text(self, db_session):
        p = _make_project(db_session)
        with pytest.raises(ValueError, match="No extracted text"):
            RequirementService.analyze_project_requirements(p.id, db_session)

    def test_extracts_requirements_with_mock(self, db_session):
        """Use the real MockProvider (LLM_PROVIDER=mock set in conftest)."""
        p = _make_project(db_session, name="Library Management System")
        _make_file(db_session, p.id)

        result = RequirementService.analyze_project_requirements(p.id, db_session)

        assert "total_extracted" in result
        assert result["total_extracted"] > 0
        assert result["functional_count"] > 0

    def test_clears_old_requirements_before_re_analysis(self, db_session):
        p = _make_project(db_session)
        _make_file(db_session, p.id)

        # Run twice; second should not double-count
        RequirementService.analyze_project_requirements(p.id, db_session)
        count_first = db_session.query(ExtractedRequirement).filter_by(project_id=p.id).count()

        RequirementService.analyze_project_requirements(p.id, db_session)
        count_second = db_session.query(ExtractedRequirement).filter_by(project_id=p.id).count()

        assert count_first == count_second


class TestGetRequirements:
    def test_returns_all_categories(self, db_session):
        p = _make_project(db_session)
        _make_file(db_session, p.id)
        RequirementService.analyze_project_requirements(p.id, db_session)

        all_reqs = RequirementService.get_requirements(p.id, None, db_session)
        assert len(all_reqs) > 0

    def test_filter_by_category(self, db_session):
        p = _make_project(db_session)
        _make_file(db_session, p.id)
        RequirementService.analyze_project_requirements(p.id, db_session)

        func_reqs = RequirementService.get_requirements(p.id, "functional", db_session)
        for r in func_reqs:
            assert r.category == "functional"

    def test_empty_project_returns_empty_list(self, db_session):
        p = _make_project(db_session)
        result = RequirementService.get_requirements(p.id, None, db_session)
        assert result == []


class TestGetSummary:
    def test_summary_counts_match_actual_records(self, db_session):
        p = _make_project(db_session)
        _make_file(db_session, p.id)
        RequirementService.analyze_project_requirements(p.id, db_session)

        summary = RequirementService.get_summary(p.id, db_session)
        reqs = RequirementService.get_requirements(p.id, None, db_session)

        assert summary.total == len(reqs)
        assert summary.functional_count == sum(1 for r in reqs if r.category == "functional")
        assert summary.non_functional_count == sum(1 for r in reqs if r.category == "non_functional")


class TestCRUD:
    def test_create_requirement(self, db_session, sample_project):
        data = RequirementCreate(
            req_id="FR-999",
            category="functional",
            title="Test FR",
            description="User shall be able to test.",
            priority="high",
        )
        req = RequirementService.create_requirement(sample_project.id, data, db_session)
        assert req.req_id == "FR-999"
        assert req.title == "Test FR"

    def test_update_requirement(self, db_session, sample_project):
        # Create first
        data = RequirementCreate(
            req_id="FR-998",
            category="functional",
            title="Original",
            description="Original description.",
            priority="low",
        )
        created = RequirementService.create_requirement(sample_project.id, data, db_session)

        update = RequirementUpdate(title="Updated Title", priority="high")
        updated = RequirementService.update_requirement(created.id, update, db_session)

        assert updated is not None
        assert updated.title == "Updated Title"
        assert updated.priority == "high"

    def test_update_nonexistent_returns_none(self, db_session):
        update = RequirementUpdate(title="No-op")
        result = RequirementService.update_requirement("nonexistent-id", update, db_session)
        assert result is None

    def test_delete_requirement(self, db_session, sample_project):
        data = RequirementCreate(
            req_id="FR-997",
            category="functional",
            title="To Delete",
            description="Will be deleted.",
            priority="medium",
        )
        created = RequirementService.create_requirement(sample_project.id, data, db_session)
        deleted = RequirementService.delete_requirement(created.id, db_session)
        assert deleted is True

    def test_delete_nonexistent_returns_false(self, db_session):
        result = RequirementService.delete_requirement("nonexistent-id", db_session)
        assert result is False
