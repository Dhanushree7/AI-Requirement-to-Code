from typing import List, Optional
from pydantic import BaseModel

class Citation(BaseModel):
    source: str  # e.g., "Library_Requirements.docx (Page 1)", "SRS Section 3.2", "DB Schema: Borrowings"
    snippet: str
    relevance_score: Optional[float] = None

class QueryRequest(BaseModel):
    question: str
    include_artifacts: bool = True
    include_graph: bool = True

class QueryResponse(BaseModel):
    question: str
    answer: str
    citations: List[Citation]
    grounded: bool = True
    confidence: str = "high"  # high | medium | low
