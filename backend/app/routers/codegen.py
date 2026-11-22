from fastapi import APIRouter, Depends, HTTPException, status
from fastapi.responses import Response
from sqlalchemy.orm import Session
from backend.app.core.database import get_db
from backend.app.core.security import get_user_project
from backend.app.models.project import Project
from backend.app.services.code_gen_service import CodeGenService

router = APIRouter(prefix="", tags=["codegen"])

@router.get("/projects/{project_id}/codegen/skeleton")
def get_backend_skeleton(
    project_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Retrieve backend starter skeleton files and AST verification status without lazy generation for an owned project."""
    try:
        return CodeGenService.get_skeleton(project_id, db)
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))

@router.get("/projects/{project_id}/codegen/download")
def download_backend_zip(
    project_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Download starter FastAPI project as a ZIP archive for an owned project."""
    try:
        zip_io = CodeGenService.create_zip_archive(project_id, db)
        return Response(
            content=zip_io.getvalue(),
            media_type="application/zip",
            headers={"Content-Disposition": f"attachment; filename=fastapi_starter_{project_id[:8]}.zip"}
        )
    except HTTPException:
        raise
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, detail=str(e))
