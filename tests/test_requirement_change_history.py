"""
Unit and integration tests for Batch 1: Requirement Change History and Deterministic Change Detection.
"""

import pytest
import json
from unittest.mock import patch
from fastapi import HTTPException

from backend.app.models.project import Project
from backend.app.models.requirement import ExtractedRequirement, RequirementChangeHistory
from backend.app.schemas.requirement import RequirementCreate, RequirementUpdate
from backend.app.services.requirement_service import RequirementService
from backend.app.routers.requirements import get_requirement_history
from tests.conftest import get_or_create_test_user


@pytest.fixture
def sample_project(db_session):
    user = get_or_create_test_user(db_session)
    project = Project(name="History Test Project", status="idle", user_id=user.id)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)
    return project


@pytest.fixture
def sample_requirement(db_session, sample_project):
    req_data = RequirementCreate(
        req_id="FR-101",
        category="functional",
        title="Initial Title",
        description="Initial requirement description.",
        priority="medium",
        module_name="AuthModule",
        is_ambiguous=False,
        ambiguity_notes=None,
        clarifying_questions=["What is the token expiration?"]
    )
    req = RequirementService.create_requirement(sample_project.id, req_data, db_session)
    return req


class TestRequirementChangeHistory:
    def test_meaningful_update_records_full_snapshots(self, db_session, sample_project, sample_requirement):
        """Updating title, description, and priority creates a change history entry with complete before/after snapshots."""
        original_uuid = sample_requirement.id
        original_logical_id = sample_requirement.req_id

        update_data = RequirementUpdate(
            title="Updated Title",
            description="Updated requirement description with new behavior.",
            priority="high",
            module_name="SecurityModule",
            is_ambiguous=True,
            ambiguity_notes="Needs review by security architect.",
            clarifying_questions=["What is the token expiration?", "Is 2FA mandatory?"]
        )

        updated = RequirementService.update_requirement(sample_requirement.id, update_data, db_session)
        assert updated is not None

        # Requirement identity must remain completely stable
        assert updated.id == original_uuid
        assert updated.req_id == original_logical_id
        assert updated.title == "Updated Title"
        assert updated.priority == "high"

        # Verify history entry
        history = db_session.query(RequirementChangeHistory).filter(
            RequirementChangeHistory.requirement_id == original_uuid
        ).all()
        assert len(history) == 1
        entry = history[0]

        # Verify snapshots
        assert entry.version_number == 1
        assert entry.req_id == "FR-101"
        assert entry.project_id == sample_project.id
        assert entry.title_before == "Initial Title"
        assert entry.title_after == "Updated Title"
        assert entry.description_before == "Initial requirement description."
        assert entry.description_after == "Updated requirement description with new behavior."
        assert entry.priority_before == "medium"
        assert entry.priority_after == "high"
        assert entry.module_name_before == "AuthModule"
        assert entry.module_name_after == "SecurityModule"
        assert entry.is_ambiguous_before is False
        assert entry.is_ambiguous_after is True
        assert entry.ambiguity_notes_before is None
        assert entry.ambiguity_notes_after == "Needs review by security architect."
        assert entry.change_type == "content_modified"
        assert "title" in entry.change_summary
        assert "description" in entry.change_summary
        assert "priority" in entry.change_summary

    def test_identical_update_is_noop_and_records_no_history(self, db_session, sample_requirement):
        """Re-submitting the exact same content does not create spurious history entries."""
        update_data = RequirementUpdate(
            title="Initial Title",
            description="Initial requirement description.",
            priority="medium",
            module_name="AuthModule",
            is_ambiguous=False
        )

        updated = RequirementService.update_requirement(sample_requirement.id, update_data, db_session)
        assert updated is not None

        history_count = db_session.query(RequirementChangeHistory).filter(
            RequirementChangeHistory.requirement_id == sample_requirement.id
        ).count()
        assert history_count == 0

    def test_multiple_sequential_updates_increment_version_numbers(self, db_session, sample_requirement):
        """Sequential edits increment version_number strictly: v1 -> v2 -> v3."""
        # 1. Edit priority
        up1 = RequirementUpdate(priority="high")
        RequirementService.update_requirement(sample_requirement.id, up1, db_session)

        # 2. Edit title
        up2 = RequirementUpdate(title="Second Title")
        RequirementService.update_requirement(sample_requirement.id, up2, db_session)

        # 3. Edit description
        up3 = RequirementUpdate(description="Third description.")
        RequirementService.update_requirement(sample_requirement.id, up3, db_session)

        history = db_session.query(RequirementChangeHistory).filter(
            RequirementChangeHistory.requirement_id == sample_requirement.id
        ).order_by(RequirementChangeHistory.version_number.asc()).all()

        assert len(history) == 3
        assert [h.version_number for h in history] == [1, 2, 3]
        assert history[0].change_type == "priority_modified"
        assert history[0].priority_before == "medium"
        assert history[0].priority_after == "high"

        assert history[1].change_type == "content_modified"
        assert history[1].title_before == "Initial Title"
        assert history[1].title_after == "Second Title"

        assert history[2].change_type == "content_modified"
        assert history[2].description_before == "Initial requirement description."
        assert history[2].description_after == "Third description."

    def test_delete_requirement_cleans_up_history_safely(self, db_session, sample_requirement):
        """Deleting a requirement cleans up its change history rows without relying on SQLite cascades."""
        up = RequirementUpdate(title="Modified Before Delete")
        RequirementService.update_requirement(sample_requirement.id, up, db_session)

        assert db_session.query(RequirementChangeHistory).filter_by(requirement_id=sample_requirement.id).count() == 1

        deleted = RequirementService.delete_requirement(sample_requirement.id, db_session)
        assert deleted is True

        assert db_session.query(ExtractedRequirement).filter_by(id=sample_requirement.id).count() == 0
        assert db_session.query(RequirementChangeHistory).filter_by(requirement_id=sample_requirement.id).count() == 0

    def test_no_llm_or_artifact_side_effects_on_update(self, db_session, sample_requirement):
        """Updating a requirement does not trigger LLM calls or artifact/graph regeneration."""
        with patch("backend.app.services.artifact_service.ArtifactService.generate_artifact") as mock_gen_art, \
             patch("backend.app.services.graph_service.GraphService.generate_knowledge_graph") as mock_graph, \
             patch("backend.app.services.llm.factory.get_llm_provider") as mock_llm:
            
            up = RequirementUpdate(title="No Side Effects Title")
            RequirementService.update_requirement(sample_requirement.id, up, db_session)

            assert not mock_gen_art.called
            assert not mock_graph.called
            assert not mock_llm.called


class TestRequirementHistoryEndpoint:
    def test_get_history_scoped_endpoint(self, db_session, sample_project, sample_requirement):
        """Scoped endpoint GET /api/projects/{project_id}/requirements/{req_id}/history returns chronological records."""
        # Update requirement twice
        up1 = RequirementUpdate(title="Endpoint Update 1")
        RequirementService.update_requirement(sample_requirement.id, up1, db_session)

        up2 = RequirementUpdate(description="Endpoint Update 2")
        RequirementService.update_requirement(sample_requirement.id, up2, db_session)

        # Query using logical req_id
        history_list = get_requirement_history(
            project_id=sample_project.id,
            req_id=sample_requirement.req_id,
            project=sample_project,
            db=db_session
        )
        assert len(history_list) == 2

        # Most recent first (version 2 then version 1)
        # Note: get_requirement_history returns Pydantic or ORM objects with attributes
        v2 = history_list[0]
        v1 = history_list[1]
        v2_ver = getattr(v2, "version_number", None) or v2["version_number"]
        v2_desc = getattr(v2, "description_after", None) or v2["description_after"]
        v1_ver = getattr(v1, "version_number", None) or v1["version_number"]
        v1_title = getattr(v1, "title_after", None) or v1["title_after"]

        assert v2_ver == 2
        assert v2_desc == "Endpoint Update 2"
        assert v1_ver == 1
        assert v1_title == "Endpoint Update 1"

        # Query using UUID
        history_uuid = get_requirement_history(
            project_id=sample_project.id,
            req_id=sample_requirement.id,
            project=sample_project,
            db=db_session
        )
        assert len(history_uuid) == 2

    def test_get_history_nonexistent_returns_404(self, db_session, sample_project):
        with pytest.raises(HTTPException) as exc:
            get_requirement_history(
                project_id=sample_project.id,
                req_id="NONEXISTENT-REQ",
                project=sample_project,
                db=db_session
            )
        assert exc.value.status_code == 404

    def test_get_history_nonexistent_project_returns_404(self, db_session):
        with pytest.raises(HTTPException) as exc:
            get_requirement_history(
                project_id="nonexistent-proj",
                req_id="FR-101",
                project=None,
                db=db_session
            )
        assert exc.value.status_code == 404
