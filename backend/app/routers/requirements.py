import json
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import get_current_user, get_user_project
from backend.app.models.user import User
from backend.app.models.project import Project
from backend.app.schemas.requirement import (
    RequirementCreate, RequirementUpdate, RequirementResponse, RequirementsSummary, RequirementHistoryResponse
)
from backend.app.models.requirement import ExtractedRequirement
from backend.app.services.requirement_service import RequirementService
from backend.app.services.graph_service import GraphService
from backend.app.services.rag_service import RagService

router = APIRouter(prefix="", tags=["requirements"])

@router.post("/projects/{project_id}/domain-model")
def create_domain_model(
    project_id: str,
    model_data: Dict[str, Any],
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Create or initialize domain model, synchronizing graph and RAG index."""
    project.domain_model_json = json.dumps(model_data)
    db.commit()

    try:
        GraphService.generate_knowledge_graph(project_id, db)
        RagService.index_project_chunks(project_id, db)
    except Exception:
        pass

    return {"status": "success", "message": "Domain model created and graph/RAG synchronized"}

@router.delete("/projects/{project_id}/domain-model", status_code=status.HTTP_204_NO_CONTENT)
def delete_domain_model(
    project_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Delete domain model for an owned project."""
    project.domain_model_json = None
    db.commit()
    return None

@router.get("/projects/{project_id}/domain-model")
def get_domain_model(
    project_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Fetch the project's current validated Domain Model."""
    if not project.domain_model_json:
        return {}
    try:
        return json.loads(project.domain_model_json)
    except Exception:
        return {}

@router.put("/projects/{project_id}/domain-model")
def update_domain_model(
    project_id: str,
    model_data: Dict[str, Any],
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Update domain model, synchronizing graph and RAG index."""
    project.domain_model_json = json.dumps(model_data)
    db.commit()

    # Re-index graph and RAG automatically when domain model is updated
    try:
        GraphService.generate_knowledge_graph(project_id, db)
        RagService.index_project_chunks(project_id, db)
    except Exception:
        pass

    return {"status": "success", "message": "Domain model updated and graph/RAG synchronized"}

@router.post("/projects/{project_id}/requirements/analyze")
def analyze_requirements(
    project_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Analyze uploaded requirement document and extract structured requirements."""
    try:
        summary = RequirementService.analyze_project_requirements(project_id, db)
        return summary
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Requirement analysis failed: {str(e)}")

@router.get("/projects/{project_id}/requirements", response_model=List[RequirementResponse])
def get_requirements(
    project_id: str,
    category: Optional[str] = None,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """List extracted requirements with optional category filtering (functional, non_functional, etc.)."""
    return RequirementService.get_requirements(project_id, category, db)

@router.get("/projects/{project_id}/requirements/summary", response_model=RequirementsSummary)
def get_requirements_summary(
    project_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Get aggregated requirements statistics and categorized items."""
    return RequirementService.get_summary(project_id, db)

@router.post("/projects/{project_id}/requirements", response_model=RequirementResponse, status_code=status.HTTP_201_CREATED)
def create_requirement(
    project_id: str,
    data: RequirementCreate,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Manually add a requirement to an owned project."""
    return RequirementService.create_requirement(project_id, data, db)

@router.put("/requirements/{req_id}", response_model=RequirementResponse)
def update_requirement(
    req_id: str,
    data: RequirementUpdate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Update requirement details, priority, or ambiguity status ensuring user owns the parent project."""
    req = db.query(ExtractedRequirement).filter(ExtractedRequirement.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    
    # Check parent project ownership
    get_user_project(req.project_id, current_user, db)

    updated = RequirementService.update_requirement(req_id, data, db)
    if not updated:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return updated

@router.delete("/requirements/{req_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_requirement(
    req_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Delete a requirement ensuring user owns the parent project."""
    req = db.query(ExtractedRequirement).filter(ExtractedRequirement.id == req_id).first()
    if not req:
        raise HTTPException(status_code=404, detail="Requirement not found")
    
    # Check parent project ownership
    get_user_project(req.project_id, current_user, db)

    success = RequirementService.delete_requirement(req_id, db)
    if not success:
        raise HTTPException(status_code=404, detail="Requirement not found")
    return None

@router.get("/projects/{project_id}/requirements/{req_id}/history", response_model=List[RequirementHistoryResponse])
def get_requirement_history(
    project_id: str,
    req_id: str,
    project: Optional[Project] = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Retrieve chronological change history for a requirement within an owned project."""
    if not project:
        raise HTTPException(status_code=404, detail="Project not found")
    req = db.query(ExtractedRequirement).filter(
        ExtractedRequirement.project_id == project_id,
        (ExtractedRequirement.req_id == req_id) | (ExtractedRequirement.id == req_id)
    ).first()
    if not req:
        raise HTTPException(status_code=404, detail=f"Requirement '{req_id}' not found in project")

    return RequirementService.get_requirement_history(project_id, req.id, db)
