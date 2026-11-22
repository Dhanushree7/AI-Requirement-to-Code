import json
from datetime import datetime
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import get_user_project
from backend.app.models.project import Project
from backend.app.schemas.artifact import (
    ArtifactResponse, ArtifactUpdateRequest, RegenerateRequest, ArtifactVersionResponse
)
from backend.app.services.artifact_service import ArtifactService
from backend.app.services.job_runner import job_manager
from backend.app.services.llm.base import LLMProviderError

router = APIRouter(prefix="", tags=["artifacts"])

@router.post("/projects/{project_id}/artifacts/generate-all", status_code=status.HTTP_202_ACCEPTED)
def generate_all_artifacts(
    project_id: str,
    project: Optional[Project] = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Start background generation job for all 6 artifacts for an owned project."""
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Project not found")

    # Prevent duplicate active generation jobs for the same project
    active_job = job_manager.get_active_job_for_project(project_id)
    if active_job:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"A generation job is already active for this project (job ID: {active_job['id']})."
        )

    def run_generation(job_id: str):
        from backend.app.core.database import SessionLocal
        worker_db = SessionLocal()
        try:
            return ArtifactService.generate_all(project_id, worker_db, job_id=job_id)
        finally:
            worker_db.close()

    try:
        job_id = job_manager.submit_job(
            task_name=f"generate_all_{project_id}",
            target=run_generation,
            project_id=project_id
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    return {
        "message": "Artifact generation started in background.",
        "job_id": job_id,
        "project_id": project_id,
        "status": "running"
    }

@router.get("/projects/{project_id}/artifacts/{artifact_type}", response_model=ArtifactResponse)
def get_artifact(
    project_id: str,
    artifact_type: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Get artifact content and version history for an owned project. Purely read-only; does not generate on GET."""
    art = ArtifactService.get_artifact(project_id, artifact_type, db)
    if not art:
        title_map = {
            "srs": "SRS Document",
            "architecture": "Architecture Suggestion",
            "schema": "Database Schema",
            "api": "API Documentation",
            "skeleton": "Backend Skeleton",
            "testcases": "Test Cases",
        }
        now = datetime.utcnow()
        return ArtifactResponse(
            id=f"pending_{project_id}_{artifact_type}",
            project_id=project_id,
            artifact_type=artifact_type,
            title=title_map.get(artifact_type, artifact_type.capitalize()),
            status="pending",
            current_version=1,
            content={},
            metadata={},
            created_at=now,
            updated_at=now,
            versions=[]
        )

    content = json.loads(art.content_json) if art.content_json else {}
    meta = json.loads(art.metadata_json) if art.metadata_json else {}

    versions = []
    if art.versions:
        for v in art.versions:
            v_content = {}
            if v.content_json:
                try:
                    v_content = json.loads(v.content_json)
                except Exception:
                    pass
            versions.append(
                ArtifactVersionResponse(
                    id=v.id,
                    version_number=v.version_number,
                    content_json=v_content,
                    changelog=v.changelog,
                    created_at=v.created_at
                )
            )

    return ArtifactResponse(
        id=art.id,
        project_id=art.project_id,
        artifact_type=art.artifact_type,
        title=art.title,
        status=art.status,
        current_version=art.current_version,
        content=content,
        metadata=meta,
        created_at=art.created_at,
        updated_at=art.updated_at,
        versions=versions
    )

@router.put("/projects/{project_id}/artifacts/{artifact_type}", response_model=ArtifactResponse)
def update_artifact(
    project_id: str,
    artifact_type: str,
    data: ArtifactUpdateRequest,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Update artifact content and commit a new version for an owned project."""
    try:
        art = ArtifactService.update_artifact(project_id, artifact_type, data.content, data.changelog, db)
        return get_artifact(project_id, artifact_type, project=project, db=db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/projects/{project_id}/artifacts/{artifact_type}/regenerate", response_model=ArtifactResponse)
def regenerate_artifact(
    project_id: str,
    artifact_type: str,
    data: RegenerateRequest,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Regenerate a single artifact using LLM provider for an owned project."""
    try:
        from backend.app.services.llm.base import cache_invalidate_project
        cache_invalidate_project(project_id)
        ArtifactService.generate_artifact(project_id, artifact_type, db, force_regenerate=True)
        return get_artifact(project_id, artifact_type, project=project, db=db)
    except LLMProviderError as e:
        raise HTTPException(status_code=502, detail=f"LLM provider error: {e}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/projects/{project_id}/artifacts/{artifact_type}/restore/{version_number}", response_model=ArtifactResponse)
def restore_version(
    project_id: str,
    artifact_type: str,
    version_number: int,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Restore a previous version of an artifact for an owned project."""
    try:
        ArtifactService.restore_version(project_id, artifact_type, version_number, db)
        return get_artifact(project_id, artifact_type, project=project, db=db)
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))
