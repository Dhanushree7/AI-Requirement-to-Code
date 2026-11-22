from datetime import datetime
from typing import List, Optional
from pydantic import BaseModel, Field, ConfigDict

class RequirementBase(BaseModel):
    req_id: str
    category: str  # functional, non_functional, actor, entity, module, constraint
    title: str
    description: str
    priority: str = "medium"
    priority_source: Optional[str] = "suggested"
    module_name: Optional[str] = None
    is_ambiguous: bool = False
    ambiguity_notes: Optional[str] = None
    clarifying_questions: Optional[List[str]] = None

class RequirementCreate(RequirementBase):
    pass

class RequirementUpdate(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    priority: Optional[str] = None
    module_name: Optional[str] = None
    is_ambiguous: Optional[bool] = None
    ambiguity_notes: Optional[str] = None
    clarifying_questions: Optional[List[str]] = None

class RequirementResponse(RequirementBase):
    id: str
    project_id: str
    created_at: datetime
    updated_at: datetime

    model_config = ConfigDict(from_attributes=True)

class RequirementsSummary(BaseModel):
    total: int
    functional_count: int
    non_functional_count: int
    actor_count: int
    entity_count: int
    module_count: int
    constraint_count: int
    ambiguous_count: int
    requirements: List[RequirementResponse]

class RequirementHistoryResponse(BaseModel):
    id: str
    requirement_id: str
    project_id: str
    req_id: str
    version_number: int
    title_before: Optional[str] = None
    title_after: Optional[str] = None
    description_before: Optional[str] = None
    description_after: Optional[str] = None
    priority_before: Optional[str] = None
    priority_after: Optional[str] = None
    module_name_before: Optional[str] = None
    module_name_after: Optional[str] = None
    is_ambiguous_before: Optional[bool] = None
    is_ambiguous_after: Optional[bool] = None
    ambiguity_notes_before: Optional[str] = None
    ambiguity_notes_after: Optional[str] = None
    clarifying_questions_before: Optional[List[str]] = None
    clarifying_questions_after: Optional[List[str]] = None
    change_type: str
    change_summary: Optional[str] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
