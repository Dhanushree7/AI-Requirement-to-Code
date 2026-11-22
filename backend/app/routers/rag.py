from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import get_user_project
from backend.app.models.project import Project
from backend.app.schemas.rag import QueryRequest, QueryResponse
from backend.app.services.rag_service import RagService

router = APIRouter(prefix="", tags=["rag"])

@router.post("/projects/{project_id}/rag/query", response_model=QueryResponse)
def query_project_rag(
    project_id: str,
    request: QueryRequest,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Query project context using RAG semantic search and cited LLM reasoning for an owned project."""
    try:
        return RagService.query_project(project_id, request, db)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"RAG query error: {str(e)}")

@router.post("/projects/{project_id}/rag/index")
def index_project_chunks(
    project_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Index document chunks into ChromaDB for an owned project."""
    try:
        RagService.index_project_chunks(project_id, db)
        return {"status": "success", "message": "Project chunks indexed in ChromaDB"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/projects/{project_id}/rag/suggested-questions")
def get_suggested_questions(
    project_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Retrieve dynamically generated, domain-specific questions for an owned project."""
    return RagService.get_suggested_questions(project_id, db)
