"""
Tests for requirement extraction completeness, consistency, and domain-agnostic safeguards.
Verifies entity/module auto-registration, duplicate prevention, ambiguous heading handling,
dashboard count accuracy, and knowledge-graph linkage across Hospital and Hotel domains.
"""
import pytest
import json
from pathlib import Path

from backend.app.models.project import Project, UploadedFile
from backend.app.models.requirement import ExtractedRequirement
from backend.app.models.artifact import Artifact
from backend.app.models.graph import GraphData
from backend.app.services.requirement_service import RequirementService, _extract_functional_modules_from_text, _map_requirements_to_modules, _extract_validated_domain_entities
from backend.app.services.project_service import ProjectService
from backend.app.services.graph_service import GraphService
from backend.app.services.artifact_service import ArtifactService
from tests.conftest import get_or_create_test_user

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_docs"

def _create_isolated_project(db, name, filename):
    user = get_or_create_test_user(db)
    p = Project(name=name, status="idle", user_id=user.id)
    db.add(p)
    db.commit()
    db.refresh(p)

    file_path = SAMPLE_DIR / filename
    text = file_path.read_text(encoding="utf-8") if file_path.exists() else f"# {name}\nRequirements text"

    f = UploadedFile(
        project_id=p.id,
        filename=filename,
        file_path=str(file_path),
        file_type="txt",
        file_size=len(text.encode("utf-8")),
        extracted_text=text,
        extraction_status="completed"
    )
    db.add(f)
    db.commit()
    return p, text


class TestExtractionCompletenessSafeguards:
    """Unit tests for domain-agnostic extraction safeguards."""

    def test_ambiguous_headings_are_excluded_from_functional_modules(self):
        text = """# Software Requirements Specification
## 1. Project Overview & Scope
General introductory text.
## 2. Assumptions & Constraints
System assumes 99.9% uptime.
## 3. Revision History
Version 1.0 initial draft.
### Module 1: Patient Admission
The system shall register new patients.
"""
        modules = _extract_functional_modules_from_text(text)
        mod_names = [m["name"] for m in modules]
        # Must exclude meta headings
        assert "Project Overview & Scope" not in mod_names
        assert "Assumptions & Constraints" not in mod_names
        assert "Revision History" not in mod_names
        # Must include the valid functional module
        assert "Patient Admission" in mod_names

    def test_unambiguous_mapping_and_ambiguous_preservation(self):
        text = """### Module 1: Booking Management
FR-001: Guests shall book rooms.
FR-002: Guests shall cancel bookings.

## 4. General Notes
FR-003: System shall maintain audit logs.
"""
        modules = [
            {"name": "Booking Management", "start": text.find("### Module 1: Booking Management"), "end": text.find("## 4. General Notes")}
        ]
        reqs = [
            {"req_id": "FR-001", "title": "Book rooms", "module_name": None},
            {"req_id": "FR-002", "title": "Cancel bookings", "module_name": None},
            {"req_id": "FR-003", "title": "Audit logs", "module_name": None},
        ]
        _map_requirements_to_modules(text, reqs, modules)

        # Unambiguous requirements inside module span are mapped
        assert reqs[0]["module_name"] == "Booking Management"
        assert reqs[1]["module_name"] == "Booking Management"
        # Ambiguous requirement outside any functional module remains None
        assert reqs[2]["module_name"] is None

    def test_duplicate_module_and_entity_prevention(self, db_session):
        user = get_or_create_test_user(db_session)
        p = Project(name="Duplicate Check Project", status="idle", user_id=user.id)
        db_session.add(p)
        db_session.commit()

        # Add initial module and entity
        r1 = ExtractedRequirement(project_id=p.id, req_id="MOD-001", category="module", title="Billing & Payments", description="Billing and payments module")
        r2 = ExtractedRequirement(project_id=p.id, req_id="ENT-001", category="entity", title="Invoice", description="Invoice domain entity")
        db_session.add_all([r1, r2])
        db_session.commit()

        # Simulate re-analysis or duplicate insertion of same title
        dup_text = """### Module 1: Billing & Payments
FR-001: System shall generate invoices.
"""
        f = UploadedFile(
            project_id=p.id,
            filename="dup.txt",
            file_path="/tmp/dup.txt",
            file_type="txt",
            file_size=len(dup_text),
            extracted_text=dup_text,
            extraction_status="completed"
        )
        db_session.add(f)
        db_session.commit()

        RequirementService.analyze_project_requirements(p.id, db_session)

        all_modules = db_session.query(ExtractedRequirement).filter(
            ExtractedRequirement.project_id == p.id,
            ExtractedRequirement.category == "module"
        ).all()
        mod_titles = [m.title.strip().lower() for m in all_modules]
        # Ensure 'billing & payments' was not duplicated
        assert mod_titles.count("billing & payments") == 1


class TestHospitalDomainExtractionCompleteness:
    """Verifies complete extraction and consistency in Healthcare domain."""

    def test_hospital_entities_and_modules_extracted(self, db_session):
        p, _ = _create_isolated_project(db_session, "Hospital Management System", "hospital_management_system.txt")
        result = RequirementService.analyze_project_requirements(p.id, db_session)

        assert result["entity_count"] >= 3, f"Expected at least 3 entities, found: {result['entity_count']}"
        assert result["module_count"] >= 3, f"Expected at least 3 modules, found: {result['module_count']}"

        reqs = db_session.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == p.id).all()
        entities = [r.title for r in reqs if r.category == "entity"]
        modules = [r.title for r in reqs if r.category == "module"]
        frs = [r for r in reqs if r.category == "functional"]

        # Assert expected domain entities
        assert any(e.lower() in ["patient", "doctor", "appointment", "prescription", "medicalrecord", "invoice"] for e in entities)
        # Assert functional requirements are mapped to modules
        mapped_frs = [r for r in frs if r.module_name is not None]
        assert len(mapped_frs) >= len(frs) * 0.7, "At least 70% of functional requirements should be mapped to modules"

    def test_hospital_knowledge_graph_linkage(self, db_session):
        p, _ = _create_isolated_project(db_session, "Hospital Management System", "hospital_management_system.txt")
        RequirementService.analyze_project_requirements(p.id, db_session)

        GraphService.generate_knowledge_graph(p.id, db_session)
        graph_data = GraphService.get_graph_data(p.id, db_session)
        nodes = graph_data["nodes"]
        edges = graph_data["edges"]

        node_types = {n.get("type") for n in nodes}
        assert "Module" in node_types, "Graph must contain Module nodes"
        assert "Database Entity" in node_types, "Graph must contain Database Entity nodes"

        # Check for 'belongs_to' edges connecting requirements to modules
        belongs_to_edges = [e for e in edges if e.get("label") == "belongs_to"]
        assert len(belongs_to_edges) > 0, "Graph must contain 'belongs_to' edges linking requirements to modules"

    def test_hospital_dashboard_counts_accuracy(self, db_session):
        p, _ = _create_isolated_project(db_session, "Hospital Management System", "hospital_management_system.txt")
        RequirementService.analyze_project_requirements(p.id, db_session)

        dashboard = ProjectService.get_dashboard_data(db_session, p.id)
        chips = {c.id: c for c in dashboard.status_chips}

        assert chips["entities"].state == "done", f"Entities chip should be done, found {chips['entities'].state}"
        assert chips["modules"].state == "done", f"Modules chip should be done, found {chips['modules'].state}"
        assert dashboard.graph_summary.entity_count > 0, "Dashboard graph summary entity_count must be > 0"


class TestHotelDomainExtractionCompleteness:
    """Verifies complete extraction and consistency in Hospitality domain."""

    def test_hotel_entities_and_modules_extracted(self, db_session):
        p, _ = _create_isolated_project(db_session, "Hotel Booking System", "hotel_booking_system.txt")
        result = RequirementService.analyze_project_requirements(p.id, db_session)

        assert result["entity_count"] >= 3, f"Expected at least 3 entities, found: {result['entity_count']}"
        assert result["module_count"] >= 3, f"Expected at least 3 modules, found: {result['module_count']}"

        reqs = db_session.query(ExtractedRequirement).filter(ExtractedRequirement.project_id == p.id).all()
        entities = [r.title for r in reqs if r.category == "entity"]
        modules = [r.title for r in reqs if r.category == "module"]
        frs = [r for r in reqs if r.category == "functional"]

        # Assert expected domain entities
        assert any(e.lower() in ["guest", "room", "reservation", "payment", "foliocharge"] for e in entities)
        # Assert functional requirements mapped to modules
        mapped_frs = [r for r in frs if r.module_name is not None]
        assert len(mapped_frs) >= len(frs) * 0.7

    def test_hotel_dashboard_and_graph_linkage(self, db_session):
        p, _ = _create_isolated_project(db_session, "Hotel Booking System", "hotel_booking_system.txt")
        RequirementService.analyze_project_requirements(p.id, db_session)

        dashboard = ProjectService.get_dashboard_data(db_session, p.id)
        chips = {c.id: c for c in dashboard.status_chips}
        assert chips["entities"].state == "done"
        assert chips["modules"].state == "done"

        GraphService.generate_knowledge_graph(p.id, db_session)
        graph_data = GraphService.get_graph_data(p.id, db_session)
        edges = graph_data["edges"]
        belongs_to_edges = [e for e in edges if e.get("label") == "belongs_to"]
        assert len(belongs_to_edges) > 0
