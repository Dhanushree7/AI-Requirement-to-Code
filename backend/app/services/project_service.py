import json
import logging
import os
from typing import List, Optional
from sqlalchemy.orm import Session
from sqlalchemy import func
from backend.app.models.project import Project, UploadedFile
from backend.app.models.requirement import ExtractedRequirement
from backend.app.models.artifact import Artifact
from backend.app.models.graph import GraphData
from backend.app.schemas.project import (
    ProjectCreate, ProjectUpdate, ProjectResponse,
    DashboardResponse, PipelineStep, StatusChip,
    ArtifactCardSummary, GraphSummary, CoverageResponse
)

logger = logging.getLogger(__name__)

class ProjectService:
    @staticmethod
    def get_projects(db: Session, user_id: Optional[str] = None) -> List[ProjectResponse]:
        query = db.query(Project)
        if user_id:
            query = query.filter(Project.user_id == user_id)
        projects = query.order_by(Project.created_at.desc()).all()
        results = []
        for p in projects:
            art_count = db.query(Artifact).filter(Artifact.project_id == p.id, Artifact.status == "completed").count()
            file_count = db.query(UploadedFile).filter(UploadedFile.project_id == p.id).count()
            results.append(
                ProjectResponse(
                    id=p.id,
                    name=p.name,
                    description=p.description,
                    status=p.status,
                    current_step=p.current_step,
                    created_at=p.created_at,
                    updated_at=p.updated_at,
                    artifact_count=art_count,
                    file_count=file_count
                )
            )
        return results

    @staticmethod
    def get_project_by_id(db: Session, project_id: str, user_id: Optional[str] = None) -> Optional[Project]:
        query = db.query(Project).filter(Project.id == project_id)
        if user_id:
            query = query.filter(Project.user_id == user_id)
        return query.first()

    @staticmethod
    def create_project(db: Session, project_data: ProjectCreate, user_id: Optional[str] = None) -> Project:
        project = Project(
            name=project_data.name,
            description=project_data.description,
            user_id=user_id,
            status="idle",
            current_step="upload"
        )
        db.add(project)
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def update_project(db: Session, project_id: str, update_data: ProjectUpdate, user_id: Optional[str] = None) -> Optional[Project]:
        query = db.query(Project).filter(Project.id == project_id)
        if user_id:
            query = query.filter(Project.user_id == user_id)
        project = query.first()
        if not project:
            return None
        if update_data.name is not None:
            project.name = update_data.name
        if update_data.description is not None:
            project.description = update_data.description
        if update_data.status is not None:
            project.status = update_data.status
        if update_data.current_step is not None:
            project.current_step = update_data.current_step
        db.commit()
        db.refresh(project)
        return project

    @staticmethod
    def safe_delete_file(candidate_path: str, trusted_base_dir: Optional[str] = None) -> bool:
        """
        Safely delete a file ensuring it is strictly contained within trusted_base_dir.
        Rejects symlinks, directories, empty paths, and paths resolving outside the base directory.
        Returns True if the file was deleted, False otherwise.
        """
        if not candidate_path or not isinstance(candidate_path, str):
            return False
        if trusted_base_dir is None:
            from backend.app.core.config import settings
            trusted_base_dir = str(settings.UPLOAD_DIR)
        try:
            base_canonical = os.path.realpath(os.path.abspath(trusted_base_dir))
            target_canonical = os.path.realpath(os.path.abspath(candidate_path))

            # Verify commonpath containment
            common = os.path.commonpath([base_canonical, target_canonical])
            if common != base_canonical or target_canonical == base_canonical:
                logger.warning(f"Refusing to delete path outside storage root: {candidate_path!r}")
                return False

            # Reject symlinks
            if os.path.islink(target_canonical) or os.path.islink(candidate_path):
                logger.warning(f"Refusing to delete symlink: {candidate_path!r}")
                return False

            # Must be a regular file
            if os.path.isfile(target_canonical):
                os.remove(target_canonical)
                return True
            return False
        except Exception as e:
            logger.error(f"Error safely deleting file {candidate_path!r}: {e}")
            return False

    @staticmethod
    def delete_project(db: Session, project_id: str, user_id: Optional[str] = None) -> bool:
        query = db.query(Project).filter(Project.id == project_id)
        if user_id:
            query = query.filter(Project.user_id == user_id)
        project = query.first()
        if not project:
            return False

        # Capture file paths belonging to this project before deletion
        file_records = db.query(UploadedFile).filter(UploadedFile.project_id == project_id).all()
        project_file_paths = [f.file_path for f in file_records if f.file_path]
        
        # Delete ChromaDB collection if present
        try:
            from backend.app.services.rag_service import RagService
            RagService.delete_project_collection(project_id)
        except Exception:
            pass

        # Commit DB deletion first (cascades to project records)
        db.delete(project)
        db.commit()

        # Safely delete exact project files after DB commit
        from backend.app.core.config import settings
        upload_root = str(settings.UPLOAD_DIR)
        for path in project_file_paths:
            ProjectService.safe_delete_file(path, upload_root)

        return True

    @staticmethod
    def get_dashboard_data(db: Session, project_id: str, user_id: Optional[str] = None) -> Optional[DashboardResponse]:
        query = db.query(Project).filter(Project.id == project_id)
        if user_id:
            query = query.filter(Project.user_id == user_id)
        project = query.first()
        if not project:
            return None

        # Uploaded file (most recent active upload)
        uploaded_file = db.query(UploadedFile).filter(
            UploadedFile.project_id == project_id
        ).order_by(UploadedFile.created_at.desc()).first()
        filename = uploaded_file.filename if uploaded_file else None

        # Requirements stats
        reqs = db.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == project_id).all()
        req_count = len(reqs)
        fr_count = sum(1 for r in reqs if r.category == "functional")
        nfr_count = sum(1 for r in reqs if r.category == "non_functional")
        ent_count = sum(1 for r in reqs if r.category == "entity")
        mod_count = sum(1 for r in reqs if r.category == "module")

        # Artifacts
        artifacts = db.query(Artifact).filter(Artifact.project_id == project_id).all()
        art_map = {a.artifact_type: a for a in artifacts}
        completed_artifacts = sum(1 for a in artifacts if a.status == "completed")

        # Define 6 standard artifact cards
        artifact_specs = [
            ("srs", "SRS Document", "Structured requirements spec generated from your upload.", "Sections"),
            ("architecture", "Architecture", "Suggested layered design - review before adopting.", "Layers"),
            ("schema", "Database Schema", "Entities and relationships derived from requirement text.", "Tables"),
            ("api", "API Documentation", "Endpoints, methods and sample payloads.", "Endpoints"),
            ("skeleton", "Backend Skeleton", "Starter FastAPI project - yours to extend, not final.", "Files"),
            ("testcases", "Test Cases", "Scenarios generated straight from the requirements.", "Cases"),
        ]

        artifact_cards = []
        for art_type, title, desc, count_label in artifact_specs:
            art = art_map.get(art_type)
            count = 0
            status = "pending"
            version = 1
            if art:
                status = art.status
                version = art.current_version
                if art.metadata_json:
                    try:
                        meta = json.loads(art.metadata_json)
                        count = meta.get("count", 0)
                    except Exception:
                        count = 0
            artifact_cards.append(
                ArtifactCardSummary(
                    type=art_type,
                    title=title,
                    description=desc,
                    count_label=count_label,
                    count=count,
                    status=status,
                    version=version
                )
            )

        # Graph stats
        graph = db.query(GraphData).filter(GraphData.project_id == project_id).first()
        nodes_count = 0
        edges_count = 0
        if graph:
            try:
                nodes = json.loads(graph.nodes_json)
                edges = json.loads(graph.edges_json)
                nodes_count = len(nodes)
                edges_count = len(edges)
            except Exception:
                pass

        graph_summary = GraphSummary(
            nodes_count=nodes_count,
            edges_count=edges_count,
            requirement_count=req_count,
            entity_count=ent_count,
            api_count=artifact_cards[3].count if len(artifact_cards) > 3 else 0,
            test_case_count=artifact_cards[5].count if len(artifact_cards) > 5 else 0
        )

        # Determine step states
        # Steps: upload, extraction, rag_llm, generation, ready
        is_uploaded = uploaded_file is not None
        has_reqs = req_count > 0
        all_generated = completed_artifacts == 6
        is_generating = any(a.status == "generating" for a in artifacts)

        upload_state = "done" if is_uploaded else "pending"
        is_error = project.status == "error"
        extract_state = "done" if has_reqs else ("in_progress" if project.status == "extracting" else ("error" if is_error else "pending"))
        rag_state = "done" if has_reqs else ("in_progress" if project.status == "extracting" else ("error" if is_error else "pending"))
        gen_state = "done" if all_generated else ("in_progress" if is_generating or (has_reqs and not all_generated and completed_artifacts > 0) else "pending")
        ready_state = "done" if (all_generated and project.status == "ready") else ("in_progress" if all_generated else "pending")

        pipeline_steps = [
            PipelineStep(id="upload", label="Upload", subtext=filename or "No file uploaded", state=upload_state),
            PipelineStep(id="extraction", label="Extraction", subtext=f"{req_count} requirements" if has_reqs else ("Extraction failed" if is_error else ("Extracting..." if project.status == "extracting" else "Pending")), state=extract_state),
            PipelineStep(id="rag_llm", label="RAG + LLM", subtext="context retrieved" if has_reqs else ("Extraction failed" if is_error else ("Pending analysis" if project.status == "extracting" else "Pending")), state=rag_state),
            PipelineStep(id="generation", label="Generation", subtext=f"{completed_artifacts} of 6 artifacts", state=gen_state),
            PipelineStep(id="ready", label="Ready", subtext="awaiting review" if all_generated else "In progress", state=ready_state),
        ]

        status_chips = [
            StatusChip(id="extracted", label="Extraction Failed" if (is_error and not has_reqs) else "Requirements Extracted", state="done" if has_reqs else ("error" if is_error else ("in_progress" if project.status == "extracting" else "pending"))),
            StatusChip(id="fr", label="Functional Requirements Identified", state="done" if fr_count > 0 else ("error" if is_error else ("in_progress" if project.status == "extracting" else "pending"))),
            StatusChip(id="nfr", label="Non-Functional Requirements Identified", state="done" if nfr_count > 0 else ("error" if is_error else ("in_progress" if project.status == "extracting" else "pending"))),
            StatusChip(id="entities", label="Entities Identified", state="done" if ent_count > 0 else ("error" if is_error else ("in_progress" if project.status == "extracting" else "pending"))),
            StatusChip(id="modules", label="Modules Generating..." if is_generating else ("Modules Identified" if mod_count > 0 else ("Modules Failed" if is_error else "Modules Pending")), state="in_progress" if is_generating else ("done" if mod_count > 0 else ("error" if is_error else "pending"))),
        ]

        # Calculate Coverage Report
        cov = ProjectService.get_coverage_report(db, project_id)
        if cov and cov.functional_requirements > 0:
            status_chips.append(
                StatusChip(
                    id="cov_endpoints",
                    label=f"API Coverage: {cov.covered_by_endpoints}/{cov.functional_requirements} ({cov.endpoint_coverage_pct:.0f}%)",
                    state="done" if cov.covered_by_endpoints >= cov.functional_requirements else ("in_progress" if cov.covered_by_endpoints > 0 else "pending")
                )
            )
            status_chips.append(
                StatusChip(
                    id="cov_tests",
                    label=f"Test Coverage: {cov.covered_by_tests}/{cov.functional_requirements} ({cov.test_coverage_pct:.0f}%)",
                    state="done" if cov.covered_by_tests >= cov.functional_requirements else ("in_progress" if cov.covered_by_tests > 0 else "pending")
                )
            )
            status_chips.append(
                StatusChip(
                    id="cov_tables",
                    label=f"Schema Coverage: {cov.covered_by_tables}/{cov.functional_requirements} ({cov.table_coverage_pct:.0f}%)",
                    state="done" if cov.covered_by_tables >= cov.functional_requirements else ("in_progress" if cov.covered_by_tables > 0 else "pending")
                )
            )

        return DashboardResponse(
            project_id=project.id,
            project_name=project.name,
            project_status=project.status,
            uploaded_file=filename,
            pipeline_steps=pipeline_steps,
            status_chips=status_chips,
            artifact_cards=artifact_cards,
            total_artifacts_generated=completed_artifacts,
            graph_summary=graph_summary,
            coverage=cov,
            disclaimer=""
        )

    @staticmethod
    def get_coverage_report(db: Session, project_id: str, user_id: Optional[str] = None) -> Optional[CoverageResponse]:
        """Compute coverage of requirements across APIs, Tests, and Database Tables."""
        query = db.query(Project).filter(Project.id == project_id)
        if user_id:
            query = query.filter(Project.user_id == user_id)
        project = query.first()
        if not project:
            return None

        reqs = db.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == project_id).all()
        total_reqs = len(reqs)
        fr_reqs = [r for r in reqs if r.category == "functional"]
        target_reqs = fr_reqs if fr_reqs else reqs
        target_ids = {r.req_id for r in target_reqs}
        total_target = len(target_ids)

        # 1. API Endpoint Coverage
        api_art = db.query(Artifact).filter(Artifact.project_id == project_id, Artifact.artifact_type == "api").first()
        covered_endpoint_ids = set()
        if api_art and api_art.content_json:
            try:
                endpoints = json.loads(api_art.content_json).get("endpoints", [])
                for ep in endpoints:
                    for rid in ep.get("requirement_ids", []):
                        if rid in target_ids:
                            covered_endpoint_ids.add(rid)
            except Exception:
                pass

        # 2. Test Cases Coverage
        tc_art = db.query(Artifact).filter(Artifact.project_id == project_id, Artifact.artifact_type == "testcases").first()
        covered_test_ids = set()
        if tc_art and tc_art.content_json:
            try:
                cases = json.loads(tc_art.content_json).get("cases", [])
                for tc in cases:
                    rid = tc.get("linked_req_id")
                    if rid in target_ids:
                        covered_test_ids.add(rid)
            except Exception:
                pass

        # 3. Database Table Coverage
        schema_art = db.query(Artifact).filter(Artifact.project_id == project_id, Artifact.artifact_type == "schema").first()
        covered_table_ids = set()
        if schema_art and schema_art.content_json:
            try:
                tables = json.loads(schema_art.content_json).get("tables", [])
                for t in tables:
                    for rid in t.get("requirement_ids", []):
                        if rid in target_ids:
                            covered_table_ids.add(rid)
            except Exception:
                pass

        uncovered_endpoint_req_ids = sorted(list(target_ids - covered_endpoint_ids))
        uncovered_test_req_ids = sorted(list(target_ids - covered_test_ids))
        uncovered_table_req_ids = sorted(list(target_ids - covered_table_ids))
        uncovered_any = sorted(list(target_ids - (covered_endpoint_ids & covered_test_ids & covered_table_ids)))

        endpoint_pct = round((len(covered_endpoint_ids) / total_target) * 100, 1) if total_target > 0 else 0.0
        test_pct = round((len(covered_test_ids) / total_target) * 100, 1) if total_target > 0 else 0.0
        table_pct = round((len(covered_table_ids) / total_target) * 100, 1) if total_target > 0 else 0.0

        return CoverageResponse(
            project_id=project_id,
            total_requirements=total_reqs,
            functional_requirements=total_target,
            covered_by_endpoints=len(covered_endpoint_ids),
            covered_by_tests=len(covered_test_ids),
            covered_by_tables=len(covered_table_ids),
            endpoint_coverage_pct=endpoint_pct,
            test_coverage_pct=test_pct,
            table_coverage_pct=table_pct,
            uncovered_endpoint_req_ids=uncovered_endpoint_req_ids,
            uncovered_test_req_ids=uncovered_test_req_ids,
            uncovered_table_req_ids=uncovered_table_req_ids,
            uncovered_ids=uncovered_any
        )
