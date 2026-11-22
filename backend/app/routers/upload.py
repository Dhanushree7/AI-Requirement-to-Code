import logging
import os
import shutil
import uuid
from pathlib import Path
from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.orm import Session
from backend.app.core.config import settings
from backend.app.core.database import get_db
from backend.app.core.security import get_user_project
from backend.app.models.project import Project, UploadedFile
from backend.app.models.rag_chunk import DocumentChunk
from backend.app.services.parser_service import ParserService
from backend.app.services.project_service import ProjectService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["upload"])

ALLOWED_EXTENSIONS = {".pdf", ".docx", ".doc", ".txt", ".md"}

@router.post("/projects/{project_id}/upload")
@router.post("/upload/{project_id}")
async def upload_document(
    project_id: str,
    file: UploadFile = File(...),
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Upload a software requirement document (PDF, DOCX, TXT) and extract text."""
    raw_filename = file.filename or ""
    clean_filename = Path(raw_filename).name.strip()
    if not clean_filename or "\x00" in clean_filename or clean_filename in (".", ".."):
        raise HTTPException(status_code=400, detail="Invalid filename")

    ext = Path(clean_filename).suffix.lower()
    if ext not in ALLOWED_EXTENSIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format '{ext}'. Allowed formats: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    upload_root = Path(settings.UPLOAD_DIR).resolve()
    os.makedirs(upload_root, exist_ok=True)

    # 1. Staged storage to protect prior uploads if extraction or DB fails
    staging_id = uuid.uuid4().hex[:12]
    staged_filename = f".staging_{project_id}_{staging_id}_{clean_filename}"
    staged_path = upload_root / staged_filename

    try:
        common = os.path.commonpath([str(upload_root), str(staged_path.resolve())])
        if common != str(upload_root):
            raise HTTPException(status_code=400, detail="Invalid storage path")
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid storage path")

    content = await file.read()
    file_size = len(content)
    max_bytes = settings.MAX_UPLOAD_SIZE_MB * 1024 * 1024
    if file_size > max_bytes:
        raise HTTPException(
            status_code=400,
            detail=f"File exceeds maximum allowed size of {settings.MAX_UPLOAD_SIZE_MB}MB"
        )

    try:
        with open(staged_path, "wb") as buffer:
            buffer.write(content)
    except Exception as io_err:
        ProjectService.safe_delete_file(str(staged_path), str(upload_root))
        logger.error(f"Failed to write staging file: {io_err}")
        raise HTTPException(status_code=500, detail="Failed to save uploaded file.")

    # 2. Extract text from staged file
    try:
        extracted_text = ParserService.extract_text(str(staged_path), ext)
        if not extracted_text or not extracted_text.strip():
            raise ValueError("Extracted text is empty or could not be decoded.")
    except Exception as extract_err:
        # Delete staging file; previous valid upload, file, and chunks remain untouched!
        ProjectService.safe_delete_file(str(staged_path), str(upload_root))
        logger.warning(f"Text extraction failed for '{clean_filename}' in project {project_id}: {extract_err}")
        raise HTTPException(
            status_code=422,
            detail=f"Failed to extract text from '{clean_filename}': {str(extract_err)}"
        )

    # 3. Finalize file path with containment validation
    target_filename = f"{project_id}_{clean_filename}"
    target_path = upload_root / target_filename

    try:
        shutil.move(str(staged_path), str(target_path))
    except Exception as move_err:
        ProjectService.safe_delete_file(str(staged_path), str(upload_root))
        logger.error(f"Failed to move staged file to final path: {move_err}")
        raise HTTPException(status_code=500, detail="Failed to finalize uploaded file.")

    # 4. Scoped database update and chunk replacement
    chunks = []
    try:
        uploaded_file = db.query(UploadedFile).filter(
            UploadedFile.project_id == project_id,
            UploadedFile.filename == clean_filename
        ).first()

        if not uploaded_file:
            uploaded_file = UploadedFile(
                project_id=project_id,
                filename=clean_filename,
                file_type=ext.replace(".", ""),
                file_size=file_size,
                file_path=str(target_path),
                extracted_text=extracted_text,
                extraction_status="completed"
            )
            db.add(uploaded_file)
        else:
            uploaded_file.file_size = file_size
            uploaded_file.file_path = str(target_path)
            uploaded_file.extracted_text = extracted_text
            uploaded_file.extraction_status = "completed"

        # Scope chunk deletion strictly to this document (preserves other uploads)
        db.query(DocumentChunk).filter(
            DocumentChunk.project_id == project_id,
            DocumentChunk.source_file == clean_filename
        ).delete()

        chunks = ParserService.chunk_text(extracted_text)
        for chunk in chunks:
            doc_chunk = DocumentChunk(
                project_id=project_id,
                source_file=clean_filename,
                chunk_index=chunk["index"],
                chunk_text=chunk["text"]
            )
            db.add(doc_chunk)

        project.current_step = "extraction"
        db.commit()
        db.refresh(uploaded_file)
    except Exception as db_err:
        db.rollback()
        logger.error(f"Database transaction failed during upload of '{clean_filename}': {db_err}")
        raise HTTPException(
            status_code=500,
            detail="Database transaction failed during document upload."
        )

    # 5. Chroma indexing with clear status reporting
    indexing_status = "indexed"
    try:
        from backend.app.services.rag_service import RagService
        RagService.index_project_chunks(project_id, db)
    except Exception as chroma_err:
        logger.warning(f"ChromaDB indexing warning for project {project_id}: {chroma_err}")
        indexing_status = "failed"

    return {
        "id": uploaded_file.id,
        "filename": uploaded_file.filename,
        "file_type": uploaded_file.file_type,
        "file_size": uploaded_file.file_size,
        "status": uploaded_file.extraction_status,
        "indexing_status": indexing_status,
        "char_count": len(extracted_text),
        "chunk_count": len(chunks),
        "preview": extracted_text[:400] + ("..." if len(extracted_text) > 400 else "")
    }

@router.get("/projects/{project_id}/files")
def list_project_files(
    project_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """List all uploaded files for an owned project with previews."""
    files = db.query(UploadedFile).filter(UploadedFile.project_id == project_id).all()
    return [
        {
            "id": f.id,
            "filename": f.filename,
            "file_type": f.file_type,
            "file_size": f.file_size,
            "status": f.extraction_status,
            "preview": (f.extracted_text[:300] + "...") if f.extracted_text else "",
            "created_at": f.created_at
        }
        for f in files
    ]

@router.delete("/projects/{project_id}/files/{file_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_project_file(
    project_id: str,
    file_id: str,
    project: Project = Depends(get_user_project),
    db: Session = Depends(get_db)
):
    """Delete an uploaded requirement document and its associated chunks for an owned project."""
    file_rec = db.query(UploadedFile).filter(
        UploadedFile.id == file_id,
        UploadedFile.project_id == project_id
    ).first()
    if not file_rec:
        raise HTTPException(status_code=404, detail="File not found")

    file_path = file_rec.file_path
    filename = file_rec.filename

    # Delete chunks scoped to this document
    db.query(DocumentChunk).filter(
        DocumentChunk.project_id == project_id,
        DocumentChunk.source_file == filename
    ).delete()

    db.delete(file_rec)
    db.commit()

    # Safely remove file from disk
    ProjectService.safe_delete_file(file_path)

    # Re-index Chroma
    try:
        from backend.app.services.rag_service import RagService
        RagService.index_project_chunks(project_id, db)
    except Exception as e:
        logger.warning(f"Chroma indexing warning after file deletion: {e}")

    return None
