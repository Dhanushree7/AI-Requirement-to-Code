from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field

class ProjectBase(BaseModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: Optional[str] = None

class ProjectCreate(ProjectBase):
    pass

class ProjectUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    status: Optional[str] = None
    current_step: Optional[str] = None

class UploadedFileResponse(BaseModel):
    id: str
    project_id: str
    filename: str
    file_type: str
    file_size: int
    extraction_status: str
    created_at: datetime

    class Config:
        from_attributes = True

class ProjectResponse(ProjectBase):
    id: str
    status: str
    current_step: str
    created_at: datetime
    updated_at: datetime
    artifact_count: int = 0
    file_count: int = 0

    class Config:
        from_attributes = True

class PipelineStep(BaseModel):
    id: str  # upload, extraction, rag_llm, generation, ready
    label: str  # Upload, Extraction, RAG + LLM, Generation, Ready
    subtext: str  # e.g., "requirements.pdf", "24 requirements", "context retrieved", "6 of 6 artifacts", "awaiting review"
    state: str  # done | in_progress | pending

class StatusChip(BaseModel):
    id: str
    label: str  # Requirements Extracted, Functional Requirements Identified, etc.
    state: str  # done | in_progress | pending

class ArtifactCardSummary(BaseModel):
    type: str  # srs, architecture, schema, api, skeleton, testcases
    title: str
    description: str
    count_label: str  # "Sections", "Layers", "Tables", "Endpoints", "Files", "Cases"
    count: int
    status: str  # completed | generating | pending | failed
    version: int = 1

class GraphSummary(BaseModel):
    nodes_count: int = 0
    edges_count: int = 0
    requirement_count: int = 0
    entity_count: int = 0
    api_count: int = 0
    test_case_count: int = 0

class CoverageResponse(BaseModel):
    project_id: str
    total_requirements: int = 0
    functional_requirements: int = 0
    covered_by_endpoints: int = 0
    covered_by_tests: int = 0
    covered_by_tables: int = 0
    endpoint_coverage_pct: float = 0.0
    test_coverage_pct: float = 0.0
    table_coverage_pct: float = 0.0
    uncovered_endpoint_req_ids: List[str] = []
    uncovered_test_req_ids: List[str] = []
    uncovered_table_req_ids: List[str] = []
    uncovered_ids: List[str] = []

class DashboardResponse(BaseModel):
    project_id: str
    project_name: str
    project_status: str
    uploaded_file: Optional[str] = None
    pipeline_steps: List[PipelineStep]
    status_chips: List[StatusChip]
    artifact_cards: List[ArtifactCardSummary]
    total_artifacts_generated: int
    graph_summary: GraphSummary
    coverage: Optional[CoverageResponse] = None
    disclaimer: str = ""
