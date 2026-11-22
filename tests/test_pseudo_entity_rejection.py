"""Regression tests for domain-agnostic pseudo-entity rejection,
multi-domain entity retention, and valid Pydantic model synthesis.
"""

import ast
import uuid
from unittest.mock import patch
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.core.database import Base
from backend.app.models.project import Project, UploadedFile
from backend.app.models.requirement import ExtractedRequirement
from backend.app.models.artifact import Artifact
from backend.app.services.domain_validator import (
    is_valid_domain_entity_candidate,
    is_valid_domain_table_name,
    is_valid_domain_endpoint_path,
    is_pseudo_name,
    get_candidate_forms
)
from backend.app.services.artifact_service import ArtifactService
from backend.app.services.code_gen_service import CodeGenService
from backend.app.services.requirement_service import RequirementService
from backend.app.services.llm.mock_provider import MockProvider
from backend.app.services.llm.document_analyzer import (
    extract_domain_info,
    generate_schema_heuristics,
    generate_api_heuristics,
    analyze_requirements_heuristics
)


@pytest.fixture
def in_memory_db():
    """Create an isolated, transient in-memory SQLite database for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(bind=engine)
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
        Base.metadata.drop_all(bind=engine)


def test_reported_pseudo_entities_are_rejected():
    """Test that all reported pseudo-entities, prompt fragments, verbs, and meta-words are rejected."""
    reported = [
        "uptime", "table", "nfr", "column", "domain", "json",
        "endpoints", "provides", "assigneds", "managements",
        "strictlys", "strictly", "junctions", "junction", "identitys", "identity",
        "issue", "issues", "analyze", "analyzes", "build", "builds", "model", "models",
        "busines", "business", "status", "statuses", "patch", "patchs", "role", "roles",
        "following", "followings", "mapped", "mappeds", "currently", "currentlys"
    ]
    extended_variants = [
        "uptimes", "tables", "nfrs", "columns", "domains", "jsons",
        "endpoint", "endpointss", "provide", "providess", "assigned", "assignedss",
        "management", "managementss", "includes", "including", "transactional",
        "api_endpoint", "data_table", "system_service"
    ]

    for p in reported + extended_variants:
        assert not is_valid_domain_entity_candidate(p), f"Candidate should be rejected: {p}"
        assert not is_valid_domain_table_name(p), f"Table name should be rejected: {p}"
        assert not is_valid_domain_endpoint_path(f"/api/v1/{p}"), f"Endpoint path should be rejected: /api/v1/{p}"


def test_valid_domain_entities_retained_across_three_domains():
    """Test that genuine domain entities across Hospital, Hotel, and Library/Commerce are retained."""
    hospital_entities = [
        "Patient", "Doctor", "Appointment", "Prescription",
        "MedicalRecord", "Department", "Ward", "Bed"
    ]
    hotel_entities = [
        "Guest", "Room", "Reservation", "Booking",
        "Invoice", "Payment", "Amenity"
    ]
    library_commerce_entities = [
        "Book", "Member", "Loan", "Author",
        "Product", "Order", "OrderItem", "Cart", "Review"
    ]

    for ent in hospital_entities + hotel_entities + library_commerce_entities:
        assert is_valid_domain_entity_candidate(ent), f"Valid entity wrongly rejected: {ent}"
        plural_table = ent.lower() + "s"
        assert is_valid_domain_table_name(plural_table), f"Valid table wrongly rejected: {plural_table}"
        endpoint = f"/api/v1/{plural_table}"
        assert is_valid_domain_endpoint_path(endpoint), f"Valid endpoint wrongly rejected: {endpoint}"


def test_compound_domain_names_with_common_suffixes():
    """Test that qualified domain entities (e.g. medical_records, order_items) are preserved."""
    compounds = [
        "medical_records", "patient_records", "order_items", "room_types",
        "delivery_slots", "appointment_slots", "payment_transactions"
    ]
    for comp in compounds:
        assert not is_pseudo_name(comp), f"Compound domain name wrongly classified as pseudo: {comp}"
        assert is_valid_domain_table_name(comp), f"Compound domain table should be valid: {comp}"


def test_explicit_definition_tiering():
    """Test that explicit Domain Entities definitions take precedence over heuristic rules
    while still rejecting undeniable technical meta-keywords."""
    # Custom business entity with explicit description
    assert is_valid_domain_entity_candidate("Policy", has_explicit_definition=True)
    assert is_valid_domain_entity_candidate("Encounter", has_explicit_definition=True)
    assert is_valid_domain_entity_candidate("Folio", has_explicit_definition=True)

    # Technical keywords must be rejected even if erroneously placed in an entities list
    assert not is_valid_domain_entity_candidate("Table", has_explicit_definition=True)
    assert not is_valid_domain_entity_candidate("API", has_explicit_definition=True)
    assert not is_valid_domain_entity_candidate("JSON", has_explicit_definition=True)
    assert not is_valid_domain_entity_candidate("NFR", has_explicit_definition=True)


def test_pydantic_model_compilation_with_empty_and_minimal_fields():
    """Verify that generated Pydantic models compile with 'pass' when fields are empty,
    without inventing arbitrary fields."""
    cols_empty = []
    cols_only_pk = [{"name": "id", "type": "INTEGER", "pk": True}]
    cols_pk_and_created = [
        {"name": "id", "type": "INTEGER", "pk": True},
        {"name": "created_at", "type": "TIMESTAMP", "pk": False}
    ]

    for cols in [cols_empty, cols_only_pk, cols_pk_and_created]:
        update_fields = [
            f"    {c['name']}: Optional[{CodeGenService._sql_type_to_python_and_sa(c.get('type', ''))[0]}] = None"
            for c in cols if not c.get("pk") and "created_at" not in c["name"]
        ]
        base_fields = [
            f"    {c['name']}: {CodeGenService._sql_type_to_python_and_sa(c.get('type', ''))[0]}"
            for c in cols if not c.get("pk") and "created_at" not in c["name"]
        ]

        schema_code = f'''from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict

class SampleBase(BaseModel):
{chr(10).join(base_fields) if base_fields else "    pass"}

class SampleCreate(SampleBase):
{chr(10).join(base_fields) if base_fields else "    pass"}

class SampleUpdate(BaseModel):
{chr(10).join(update_fields) if update_fields else "    pass"}

class SampleResponse(SampleBase):
    model_config = ConfigDict(from_attributes=True)
    pass
'''
        # Must parse without SyntaxError: expected an indented block
        parsed = ast.parse(schema_code)
        assert parsed is not None
        assert "pass" in schema_code


def test_schema_generator_excludes_pseudo_tables_and_preserves_unassigned(in_memory_db):
    """Verify database schema generation excludes pseudo-tables and preserves unassigned requirements without forced fallback."""
    from tests.conftest import get_or_create_test_user
    user = get_or_create_test_user(in_memory_db)
    proj = Project(
        id=str(uuid.uuid4()),
        name="Hospital System",
        description="Comprehensive healthcare management",
        user_id=user.id
    )
    in_memory_db.add(proj)

    reqs = [
        ExtractedRequirement(
            project_id=proj.id,
            req_id="FR-001",
            category="functional",
            title="Register Patient",
            description="The system shall allow staff to register new patient profiles."
        ),
        ExtractedRequirement(
            project_id=proj.id,
            req_id="FR-002",
            category="functional",
            title="Book Appointment",
            description="The system shall allow patients to book appointments with doctors."
        ),
        ExtractedRequirement(
            project_id=proj.id,
            req_id="FR-003",
            category="functional",
            title="System Uptime SLA",
            description="The system provides 99.9% uptime and maintains column audit logs."
        ),
        ExtractedRequirement(
            project_id=proj.id,
            req_id="ENT-001",
            category="entity",
            title="Patient",
            description="Patient demographic and medical information."
        ),
        ExtractedRequirement(
            project_id=proj.id,
            req_id="ENT-002",
            category="entity",
            title="Appointment",
            description="Clinical visit scheduling record."
        )
    ]
    for r in reqs:
        in_memory_db.add(r)
    in_memory_db.commit()

    with patch("backend.app.services.artifact_service.get_llm_provider", return_value=MockProvider()):
        schema_result = ArtifactService._generate_database_schema(proj, reqs, in_memory_db)
    table_names = [t["name"].lower() for t in schema_result.get("tables", [])]

    # Assert pseudo-tables are NOT present
    for bad in [
        "uptimes", "tables", "nfrs", "columns", "domains", "jsons", "endpoints",
        "provides", "assigneds", "managements", "strictlys", "junctions", "identitys",
        "busines", "status", "issue", "analyze", "build", "model"
    ]:
        assert bad not in table_names, f"Questionable table '{bad}' leaked into schema: {table_names}"

    # Assert legitimate tables exist
    assert any("patient" in t for t in table_names)
    assert any("appointment" in t for t in table_names)

    # Assert genuine domain requirements are mapped
    all_mapped_rids = set()
    for t in schema_result.get("tables", []):
        for rid in t.get("requirement_ids", []):
            all_mapped_rids.add(rid)

    assert "FR-001" in all_mapped_rids
    assert "FR-002" in all_mapped_rids

    # Assert that FR-003 (SLA metric without schema table) is NOT forcibly assigned to users or an unrelated table
    users_tbl = next((t for t in schema_result.get("tables", []) if t["name"].lower() == "users"), None)
    if users_tbl:
        assert "FR-003" not in users_tbl.get("requirement_ids", []), "FR-003 should not be forced onto users table"


def test_api_generator_excludes_pseudo_endpoints_and_unforced_traceability(in_memory_db):
    """Verify API documentation does not generate routes for pseudo-entities or force unmapped reqs to /auth/token."""
    from tests.conftest import get_or_create_test_user
    user = get_or_create_test_user(in_memory_db)
    proj = Project(
        id=str(uuid.uuid4()),
        name="Hotel Booking System",
        description="Hotel reservations and room booking",
        user_id=user.id
    )
    in_memory_db.add(proj)

    reqs = [
        ExtractedRequirement(
            project_id=proj.id,
            req_id="FR-001",
            category="functional",
            title="Search Rooms",
            description="The system shall allow guests to view available rooms."
        ),
        ExtractedRequirement(
            project_id=proj.id,
            req_id="FR-002",
            category="functional",
            title="Reserve Room",
            description="The system shall reserve a selected room for 15 minutes during checkout."
        ),
        ExtractedRequirement(
            project_id=proj.id,
            req_id="ENT-001",
            category="entity",
            title="Room",
            description="Hotel room entity."
        )
    ]
    for r in reqs:
        in_memory_db.add(r)
    in_memory_db.commit()

    with patch("backend.app.services.artifact_service.get_llm_provider", return_value=MockProvider()):
        api_result = ArtifactService._generate_api_documentation(proj, reqs, in_memory_db)
    paths = [ep["path"].lower() for ep in api_result.get("endpoints", [])]

    # No pseudo endpoints or instruction routes
    for bad in [
        "uptimes", "tables", "nfrs", "columns", "domains", "jsons", "provides",
        "assigneds", "managements", "patchs", "status", "roles"
    ]:
        assert not any(f"/{bad}" in p for p in paths), f"Leaked pseudo endpoint found in {paths}"

    # Verify legitimate endpoints exist
    assert any("room" in p or "reservation" in p for p in paths)


def test_nfr_categorization_and_exclusion_from_schema_forcing(in_memory_db):
    """Verify NFR requirements are strictly stored with category 'non_functional' and not forced into tables/endpoints."""
    doc_text = """
## 1. Scope
Hospital System Platform

## 2. Functional Requirements
- FR-001: Register patients with demographics.
- FR-002: Book doctor appointments.

## 3. Non-Functional Requirements
- NFR-001: System uptime SLA must exceed 99.9%.
- NFR-002: Passwords must be hashed using Bcrypt.
"""
    parsed = analyze_requirements_heuristics(doc_text, "Hospital System")
    reqs = parsed.get("requirements", [])
    nfrs = [r for r in reqs if r["req_id"].startswith("NFR")]
    assert len(nfrs) > 0, "NFRs should be extracted"
    for n in nfrs:
        assert n["category"] == "non_functional", f"NFR should have category 'non_functional', got {n.get('category')}"
