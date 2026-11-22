"""Domain Model schema definitions for validated requirement extraction."""

from typing import List, Optional, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DomainSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    domain_name: str = Field(description="Name/topic of the domain e.g. Hospital Management, Banking, etc.")
    overview: str = Field(description="Comprehensive domain summary derived strictly from requirements")
    assumptions: List[str] = Field(default_factory=list, description="Missing information or assumptions made")


class ActorModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    req_id: str = Field(description="ACT-001, ACT-002, etc.")
    title: str = Field(description="Actor/Role title")
    description: str = Field(description="Actor role and permissions in system")


class RequirementItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    req_id: str = Field(description="FR-001, NFR-001, etc.")
    category: str = Field(default="functional", description="functional | non_functional")
    title: str
    description: str
    priority: str = Field(default="medium", description="high | medium | low")
    module_name: Optional[str] = None
    is_ambiguous: bool = False
    ambiguity_notes: Optional[str] = None
    clarifying_questions: List[str] = Field(default_factory=list)


class AttributeModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    name: str
    data_type: str
    is_primary_key: bool = False
    is_foreign_key: bool = False
    is_nullable: bool = True
    description: Optional[str] = None


class RelationshipModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    target_entity: str
    relationship_type: str = Field(description="1:1, 1:N, N:M")
    description: Optional[str] = None


class EntityModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    req_id: str = Field(description="ENT-001, ENT-002, etc.")
    name: str = Field(description="Entity name in PascalCase or lowercase")
    description: str
    attributes: List[AttributeModel] = Field(default_factory=list)
    relationships: List[RelationshipModel] = Field(default_factory=list)


class BusinessRule(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rule_id: str = Field(description="BR-001, BR-002, etc.")
    title: str
    description: str
    enforced_by_module: Optional[str] = None


class StateTransition(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    from_state: str
    to_state: str
    trigger_action: str
    allowed_roles: List[str] = Field(default_factory=list)


class WorkflowModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    workflow_id: str = Field(description="WF-001, WF-002, etc.")
    title: str
    description: str
    entity_name: Optional[str] = None
    initial_state: str
    terminal_states: List[str] = Field(default_factory=list)
    transitions: List[StateTransition] = Field(default_factory=list)


class ModuleModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    req_id: Optional[str] = Field(default=None, description="MOD-001, MOD-002, etc.")
    name: str = Field(description="Module name")
    description: str = Field(description="Module responsibilities and scope")


class DomainModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    summary: DomainSummary
    actors: List[ActorModel] = Field(default_factory=list)
    requirements: List[RequirementItem] = Field(default_factory=list)
    entities: List[EntityModel] = Field(default_factory=list)
    modules: List[ModuleModel] = Field(default_factory=list)
    constraints: List[RequirementItem] = Field(default_factory=list)
    business_rules: List[BusinessRule] = Field(default_factory=list)
    workflows: List[WorkflowModel] = Field(default_factory=list)
