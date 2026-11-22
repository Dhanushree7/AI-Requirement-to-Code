"""
Tests for background artifact generation jobs with incremental dashboard status updates.
"""

import time
import pytest
from unittest.mock import patch
from fastapi import HTTPException

from backend.app.models.project import Project
from backend.app.models.requirement import ExtractedRequirement
from backend.app.models.artifact import Artifact
from backend.app.services.job_runner import job_manager
from backend.app.services.artifact_service import ArtifactService
from backend.app.services.project_service import ProjectService
from backend.app.routers.artifacts import generate_all_artifacts
from backend.app.routers.projects import get_active_project_job, get_job_status
from tests.conftest import get_or_create_test_user


@pytest.fixture(autouse=True)
def clean_job_manager():
    """Ensure in-memory job state is reset between tests."""
    job_manager.clear_jobs()
    yield
    job_manager.clear_jobs()


@pytest.fixture
def project_with_requirements(db_session):
    user = get_or_create_test_user(db_session)
    project = Project(name="Background Job Test Project", status="idle", current_step="rag_llm", user_id=user.id)
    db_session.add(project)
    db_session.commit()
    db_session.refresh(project)

    # Add requirements
    req1 = ExtractedRequirement(
        project_id=project.id,
        req_id="FR-001",
        category="functional",
        title="User Registration",
        description="Users register with email and password.",
        priority="high"
    )
    req2 = ExtractedRequirement(
        project_id=project.id,
        req_id="FR-002",
        category="functional",
        title="Order Processing",
        description="Place order and deduct inventory.",
        priority="high"
    )
    db_session.add_all([req1, req2])
    db_session.commit()
    return project


class TestJobManagerUnit:
    def test_job_submission_and_progress_lifecycle(self):
        """JobManager correctly tracks queued/running, progress updates, and terminal state."""
        def dummy_task(job_id):
            job_manager.update_progress(job_id, 25.0, "Step 1 done")
            job_manager.update_progress(job_id, 50.0, "Step 2 done")
            return {"status": "ok", "items": 2}

        job_id = job_manager.submit_job("dummy_task", dummy_task, project_id="proj-123")
        assert job_id is not None

        # Give background worker thread a moment to finish
        for _ in range(50):
            job = job_manager.get_job(job_id)
            if job and job["status"] == "completed":
                break
            time.sleep(0.01)

        final_job = job_manager.get_job(job_id)
        assert final_job["status"] == "completed"
        assert final_job["progress"] == 100.0
        assert final_job["result"] == {"status": "ok", "items": 2}

    def test_duplicate_job_prevention_for_same_project(self):
        """Submitting a second job for the same project while one is active raises ValueError."""
        # Manually register an active running job
        job_manager.jobs["active-job-1"] = {
            "id": "active-job-1",
            "project_id": "proj-dup-check",
            "status": "running",
            "progress": 20.0,
            "message": "Generating...",
        }

        with pytest.raises(ValueError) as exc:
            job_manager.submit_job("another_task", lambda jid: None, project_id="proj-dup-check")

        assert "already exists for project proj-dup-check" in str(exc.value)

    def test_job_failure_on_exception(self):
        """Uncaught exception in task worker transitions job to failed with clear error message."""
        def failing_task(job_id):
            raise RuntimeError("Database connection timed out")

        job_id = job_manager.submit_job("failing_task", failing_task, project_id="proj-fail")

        for _ in range(50):
            job = job_manager.get_job(job_id)
            if job and job["status"] == "failed":
                break
            time.sleep(0.01)

        failed_job = job_manager.get_job(job_id)
        assert failed_job["status"] == "failed"
        assert "Database connection timed out" in failed_job["error"]

    def test_partial_generation_errors_result_in_failed_job_state(self):
        """If target returns errors dict, JobManager marks job failed without silent success."""
        def partial_task(job_id):
            return {
                "status": "partial",
                "artifacts": {"srs": "completed", "schema": "error"},
                "errors": ["schema: LLM generation timeout"]
            }

        job_id = job_manager.submit_job("partial_task", partial_task, project_id="proj-partial")

        for _ in range(50):
            job = job_manager.get_job(job_id)
            if job and job["status"] == "failed":
                break
            time.sleep(0.01)

        job = job_manager.get_job(job_id)
        assert job["status"] == "failed"
        assert "schema: LLM generation timeout" in job["error"]
        assert job["result"]["status"] == "partial"


class TestBackgroundGenerationApiHandlers:
    def test_generate_all_returns_prompt_response_with_job_id(self, db_session, project_with_requirements):
        """generate_all_artifacts returns immediately with job ID, running status, and project ID."""
        with patch("backend.app.services.artifact_service.ArtifactService.generate_all") as mock_gen_all:
            mock_gen_all.return_value = {"status": "completed", "artifacts": {}}

            start_t = time.time()
            res = generate_all_artifacts(project_with_requirements.id, project=project_with_requirements, db=db_session)
            elapsed = time.time() - start_t

            assert "job_id" in res
            assert res["status"] == "running"
            assert res["project_id"] == project_with_requirements.id
            assert elapsed < 0.5

    def test_duplicate_generation_request_raises_409(self, db_session, project_with_requirements):
        """Triggering Generate All while a job is running for the project raises HTTP 409 Conflict."""
        job_manager.jobs["existing-running-job"] = {
            "id": "existing-running-job",
            "project_id": project_with_requirements.id,
            "status": "running",
            "progress": 33.3,
            "message": "Generating Architecture..."
        }

        with pytest.raises(HTTPException) as exc:
            generate_all_artifacts(project_with_requirements.id, project=project_with_requirements, db=db_session)

        assert exc.value.status_code == 409
        assert "already active for this project" in str(exc.value.detail)

    def test_generate_all_nonexistent_project_raises_404(self, db_session):
        """Generating artifacts for non-existent project returns 404."""
        with pytest.raises(HTTPException) as exc:
            generate_all_artifacts("non-existent-proj-id", project=None, db=db_session)
        assert exc.value.status_code == 404

    def test_get_active_job_endpoint(self, db_session, project_with_requirements):
        """get_active_project_job returns active job when running, or inactive flag when none."""
        # 1. No active job
        res_none = get_active_project_job(project_with_requirements.id, project=project_with_requirements)
        assert res_none["active"] is False
        assert res_none["job"] is None

        # 2. With active job
        job_manager.jobs["test-active-123"] = {
            "id": "test-active-123",
            "project_id": project_with_requirements.id,
            "status": "running",
            "progress": 50.0,
            "message": "Generated Database Schema (3 of 6 artifacts)",
            "started_at": "2026-11-04T10:00:00"
        }

        res_active = get_active_project_job(project_with_requirements.id, project=project_with_requirements)
        assert res_active["id"] == "test-active-123"
        assert res_active["status"] == "running"
        assert res_active["progress"] == 50.0

    def test_get_job_status_endpoint(self, db_session, project_with_requirements):
        """get_job_status returns full job status dictionary for owned project."""
        user = get_or_create_test_user(db_session)
        job_manager.jobs["poll-job-456"] = {
            "id": "poll-job-456",
            "project_id": project_with_requirements.id,
            "task_name": "generate_all",
            "status": "running",
            "progress": 66.7,
            "message": "Generated API Documentation (4 of 6 artifacts)",
            "result": None,
            "error": None
        }

        job = get_job_status("poll-job-456", current_user=user, db=db_session)
        assert job["id"] == "poll-job-456"
        assert job["progress"] == 66.7
        assert "4 of 6" in job["message"]

    def test_get_nonexistent_job_raises_404(self, db_session):
        user = get_or_create_test_user(db_session)
        with pytest.raises(HTTPException) as exc:
            get_job_status("non-existent-job-uuid", current_user=user, db=db_session)
        assert exc.value.status_code == 404


class TestIncrementalArtifactPersistenceAndDashboard:
    def test_progress_updates_and_incremental_dashboard_counts(self, db_session, project_with_requirements):
        """ArtifactService.generate_all updates job progress incrementally and commits artifacts individually."""
        progress_records = []

        def mock_generate_artifact(proj_id, art_type, db):
            art = Artifact(
                project_id=proj_id,
                artifact_type=art_type,
                title=art_type.capitalize(),
                status="completed",
                current_version=1,
                metadata_json='{"count": 5}'
            )
            db.add(art)
            db.commit()
            return art

        with patch("backend.app.services.artifact_service.ArtifactService.generate_artifact", side_effect=mock_generate_artifact), \
             patch("backend.app.services.graph_service.GraphService.generate_knowledge_graph"), \
             patch("backend.app.services.rag_service.RagService.index_project_chunks"):

            # Seed a job in job manager
            job_id = "test-progress-job"
            job_manager.jobs[job_id] = {
                "id": job_id,
                "project_id": project_with_requirements.id,
                "status": "running",
                "progress": 0.0,
                "message": "Starting..."
            }

            result = ArtifactService.generate_all(
                project_id=project_with_requirements.id,
                db=db_session,
                job_id=job_id
            )

            assert result["status"] == "completed"
            assert len(result["artifacts"]) == 6

            # Verify final job progress
            job = job_manager.get_job(job_id)
            assert job["progress"] == 100.0
            assert "Generated Test Cases (6 of 6 artifacts)" in job["message"]

            # Verify dashboard reports all 6 completed
            dashboard = ProjectService.get_dashboard_data(db_session, project_with_requirements.id)
            assert dashboard.total_artifacts_generated == 6
            gen_step = next(s for s in dashboard.pipeline_steps if s.id == "generation")
            assert gen_step.state == "done"
            assert gen_step.subtext == "6 of 6 artifacts"

    def test_partial_generation_failure_preserves_completed_and_reflects_in_dashboard(self, db_session, project_with_requirements):
        """When generation encounters errors on some artifacts, completed artifacts remain persisted and dashboard reflects partial count."""
        def mock_generate_with_failure(proj_id, art_type, db):
            # Succeed on srs and architecture, fail on schema and subsequent
            if art_type in ["srs", "architecture"]:
                art = Artifact(
                    project_id=proj_id,
                    artifact_type=art_type,
                    title=art_type.capitalize(),
                    status="completed",
                    current_version=1,
                    metadata_json='{"count": 3}'
                )
                db.add(art)
                db.commit()
                return art
            else:
                raise RuntimeError(f"Simulated failure on {art_type}")

        with patch("backend.app.services.artifact_service.ArtifactService.generate_artifact", side_effect=mock_generate_with_failure), \
             patch("backend.app.services.graph_service.GraphService.generate_knowledge_graph"), \
             patch("backend.app.services.rag_service.RagService.index_project_chunks"):

            job_id = "partial-job-789"
            job_manager.jobs[job_id] = {
                "id": job_id,
                "project_id": project_with_requirements.id,
                "status": "running",
                "progress": 0.0,
                "message": "Starting..."
            }

            result = ArtifactService.generate_all(
                project_id=project_with_requirements.id,
                db=db_session,
                job_id=job_id
            )

            assert result["status"] == "partial"
            assert len(result["errors"]) == 4  # schema, api, skeleton, testcases failed
            assert result["artifacts"]["srs"] == "completed"
            assert result["artifacts"]["architecture"] == "completed"

            # Check dashboard reflection: exactly 2 artifacts persisted
            dashboard = ProjectService.get_dashboard_data(db_session, project_with_requirements.id)
            assert dashboard.total_artifacts_generated == 2
            gen_step = next(s for s in dashboard.pipeline_steps if s.id == "generation")
            assert gen_step.state == "in_progress"
            assert gen_step.subtext == "2 of 6 artifacts"
