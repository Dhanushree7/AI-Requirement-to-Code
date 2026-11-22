from datetime import datetime
from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class ArtifactVersionResponse(BaseModel):
    id: str
    version_number: int
    content_json: Dict[str, Any]
    changelog: Optional[str] = None
    created_at: datetime

    class Config:
        from_attributes = True

class ArtifactResponse(BaseModel):
    id: str
    project_id: str
    artifact_type: str  # srs, architecture, schema, api, skeleton, testcases
    title: str
    status: str
    current_version: int
    content: Optional[Dict[str, Any]] = None
    metadata: Optional[Dict[str, Any]] = None
    created_at: datetime
    updated_at: datetime
    versions: Optional[List[ArtifactVersionResponse]] = None

    class Config:
        from_attributes = True

class ArtifactUpdateRequest(BaseModel):
    content: Dict[str, Any]
    changelog: Optional[str] = "Manual user update"

class RegenerateRequest(BaseModel):
    instructions: Optional[str] = None
    model_override: Optional[str] = None
