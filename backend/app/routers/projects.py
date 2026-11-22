from typing import List
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, get_user_project
from backend.app.models.user import User
from backend.app.models.project import Project
from backend.app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse, DashboardResponse, CoverageResponse
)
from backend.app.services.project_service import ProjectService
from backend.app.services.job_runner import job_manager

router = APIRouter(prefix="/projects", tags=["projects"])

@router.get("/jobs/{job_id}")
def get_job_status(job_id: str, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Poll status of a background generation job for an owned project."""
    job = job_manager.get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Verify that the job's project belongs to the current user
    proj_id = job.get("project_id")
    if proj_id:
        get_user_project(proj_id, current_user, db)
    return job

@router.get("/{project_id}/jobs/active")
def get_active_project_job(
    project_id: str,
    project: Project = Depends(get_user_project)
):
    """Retrieve the currently active background generation job for a project, if any."""
    job = job_manager.get_active_job_for_project(project_id)
    return job or {"active": False, "job": None}

@router.get("", response_model=List[ProjectResponse])
def list_projects(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """List all projects owned by the authenticated user."""
    return ProjectService.get_projects(db, user_id=current_user.id)

@router.post("", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def create_project(
    project_data: ProjectCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Create a new project owned by the authenticated user."""
    project = ProjectService.create_project(db, project_data, user_id=current_user.id)
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        current_step=project.current_step,
        created_at=project.created_at,
        updated_at=project.updated_at,
        artifact_count=0,
        file_count=0
    )

@router.get("/{project_id}", response_model=ProjectResponse)
def get_project(
    project_id: str,
    project: Project = Depends(get_user_project),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get project details for an owned project."""
    projects = ProjectService.get_projects(db, user_id=current_user.id)
    for p in projects:
        if p.id == project_id:
            return p
    return ProjectResponse(
        id=project.id,
        name=project.name,
        description=project.description,
        status=project.status,
        current_step=project.current_step,
        created_at=project.created_at,
        updated_at=project.updated_at,
        artifact_count=0,
        file_count=0
    )

@router.put("/{project_id}", response_model=ProjectResponse)
def update_project(
    project_id: str,
    update_data: ProjectUpdate,
    project: Project = Depends(get_user_project),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update project metadata for an owned project."""
    updated = ProjectService.update_project(db, project_id, update_data, user_id=current_user.id)
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found")
    projects = ProjectService.get_projects(db, user_id=current_user.id)
    for p in projects:
        if p.id == project_id:
            return p
    return ProjectResponse(
        id=updated.id,
        name=updated.name,
        description=updated.description,
        status=updated.status,
        current_step=updated.current_step,
        created_at=updated.created_at,
        updated_at=updated.updated_at
    )

@router.delete("/{project_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project(
    project_id: str,
    project: Project = Depends(get_user_project),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a project and its associated files/artifacts."""
    success = ProjectService.delete_project(db, project_id, user_id=current_user.id)
    if not success:
        raise HTTPException(status_code=404, detail="Project not found")
    return None

@router.get("/{project_id}/dashboard", response_model=DashboardResponse)
def get_project_dashboard(
    project_id: str,
    project: Project = Depends(get_user_project),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get full dashboard data matching UI specification."""
    data = ProjectService.get_dashboard_data(db, project_id, user_id=current_user.id)
    if not data:
        raise HTTPException(status_code=404, detail="Project not found")
    return data

@router.get("/{project_id}/coverage", response_model=CoverageResponse)
def get_project_coverage(
    project_id: str,
    project: Project = Depends(get_user_project),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Compute and retrieve requirements coverage across APIs, Test Cases, and Database Tables."""
    cov = ProjectService.get_coverage_report(db, project_id, user_id=current_user.id)
    if not cov:
        raise HTTPException(status_code=404, detail="Project not found")
    return cov
