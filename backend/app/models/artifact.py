import uuid
from datetime import datetime
from sqlalchemy import Column, String, Integer, DateTime, Text, ForeignKey
from sqlalchemy.orm import relationship
from backend.app.core.database import Base

class Artifact(Base):
    __tablename__ = "artifacts"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    project_id = Column(String(36), ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    artifact_type = Column(String(50), nullable=False)  # srs, architecture, schema, api, skeleton, testcases
    title = Column(String(255), nullable=False)
    status = Column(String(50), default="pending")  # pending, generating, completed, failed
    current_version = Column(Integer, default=1)
    content_json = Column(Text, nullable=True)  # JSON-encoded artifact content
    metadata_json = Column(Text, nullable=True)  # JSON-encoded statistics (sections, tables, endpoints, etc.)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    project = relationship("Project", back_populates="artifacts")
    versions = relationship("ArtifactVersion", back_populates="artifact", cascade="all, delete-orphan", order_by="desc(ArtifactVersion.version_number)")

class ArtifactVersion(Base):
    __tablename__ = "artifact_versions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    artifact_id = Column(String(36), ForeignKey("artifacts.id", ondelete="CASCADE"), nullable=False)
    version_number = Column(Integer, nullable=False)
    content_json = Column(Text, nullable=False)
    changelog = Column(Text, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)

    artifact = relationship("Artifact", back_populates="versions")
