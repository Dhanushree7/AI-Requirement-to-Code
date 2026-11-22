from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import get_user_project
from backend.app.models.project import Project
from backend.app.services.graph_service import GraphService
from backend.app.schemas.graph import ImpactAnalysisResult

router = APIRouter(prefix="", tags=["graph"])

@router.get("/projects/{project_id}/graph")
def get_knowledge_graph(
    project_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Retrieve graph nodes, edges, and domain entity links for an owned project."""
    try:
        return GraphService.get_graph_data(project_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/graph/traceability")
def get_traceability_matrix(
    project_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Retrieve end-to-end Traceability Matrix for an owned project."""
    try:
        data = GraphService.get_graph_data(project_id, db)
        return data.get("matrix", [])
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/graph/impact/{node_id}", response_model=ImpactAnalysisResult)
def get_impact_analysis(
    project_id: str,
    node_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Analyze change blast radius and affected downstream artifacts for a node in an owned project."""
    try:
        return GraphService.get_impact_analysis(project_id, node_id, db)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
