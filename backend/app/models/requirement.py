import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, Boolean, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

class ExtractedRequirement(Base):
    __tablename__ = "extracted_requirements"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    req_id = Column(String(50), nullable=False)  # e.g. FR-001, NFR-001, ACT-001, ENT-001, MOD-001
    category = Column(String(50), nullable=False)  # functional, non_functional, actor, entity, module, constraint
    title = Column(String(255), nullable=False)
    description = Column(Text, nullable=False)
    priority = Column(String(50), default="medium")  # high, medium, low
    priority_source = Column(String(50), default="suggested")  # document, suggested
    module_name = Column(String(100), nullable=True)  # associated module
    is_ambiguous = Column(Boolean, default=False)
    ambiguity_notes = Column(Text, nullable=True)
    clarifying_questions = Column(Text, nullable=True)  # JSON-serialized list of strings
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="requirements")
    history = relationship(
        "RequirementChangeHistory",
        back_populates="requirement",
        cascade="all, delete-orphan",
        order_by="desc(RequirementChangeHistory.version_number)"
    )

class RequirementChangeHistory(Base):
    __tablename__ = "requirement_change_history"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    requirement_id = Column(String(36), ForeignKey("extracted_requirements.id", ondelete="CASCADE"), nullable=False, index=True)
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False, index=True)
    req_id = Column(String(50), nullable=False, index=True)
    version_number = Column(Integer, nullable=False)

    # Complete before-and-after snapshots of all editable fields
    title_before = Column(String(255), nullable=True)
    title_after = Column(String(255), nullable=True)
    description_before = Column(Text, nullable=True)
    description_after = Column(Text, nullable=True)
    priority_before = Column(String(50), nullable=True)
    priority_after = Column(String(50), nullable=True)
    module_name_before = Column(String(100), nullable=True)
    module_name_after = Column(String(100), nullable=True)
    is_ambiguous_before = Column(Boolean, nullable=True)
    is_ambiguous_after = Column(Boolean, nullable=True)
    ambiguity_notes_before = Column(Text, nullable=True)
    ambiguity_notes_after = Column(Text, nullable=True)
    clarifying_questions_before = Column(Text, nullable=True)
    clarifying_questions_after = Column(Text, nullable=True)

    # Change classification & metadata
    change_type = Column(String(50), nullable=False, default="content_modified")  # content_modified, priority_modified, metadata_modified
    change_summary = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    requirement = relationship("ExtractedRequirement", back_populates="history")
