from typing import List, Optional, Dict, Any
from pydantic import BaseModel

class GraphNode(BaseModel):
    id: str
    label: str
    type: str  # Requirement, Actor, Module, API, Database Entity, Test Case
    category: Optional[str] = None
    data: Optional[Dict[str, Any]] = None

class GraphEdge(BaseModel):
    id: str
    source: str
    target: str
    label: str  # uses, belongs_to, exposes, uses_entity, verified_by, relates_to
    type: Optional[str] = "default"

class TraceabilityRow(BaseModel):
    requirement_id: str
    requirement_title: str
    category: str
    module: Optional[str] = None
    apis: List[str] = []
    entities: List[str] = []
    test_cases: List[str] = []
    coverage_status: str = "complete"  # complete | partial | unmapped | uncovered

class ImpactAnalysisResult(BaseModel):
    selected_node_id: str
    selected_node_type: str
    affected_nodes: List[GraphNode]
    affected_edges: List[GraphEdge]
    impact_summary: str

class GraphResponse(BaseModel):
    nodes: List[GraphNode]
    edges: List[GraphEdge]
    stats: Dict[str, int]
