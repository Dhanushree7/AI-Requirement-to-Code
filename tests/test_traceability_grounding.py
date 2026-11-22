import uuid
import json
import pytest
from unittest.mock import MagicMock, patch

from backend.app.models.project import Project
from backend.app.models.requirement import ExtractedRequirement
from backend.app.models.artifact import Artifact
from backend.app.models.graph import GraphData
from backend.app.services.graph_service import GraphService
from backend.app.services.artifact_service import ArtifactService
from backend.app.services.project_service import ProjectService
from tests.conftest import get_or_create_test_user


class MockLLMProvider:
    """Mock LLM Provider that returns minimal valid JSON structures."""
    def generate_json(self, prompt: str, system_prompt: str = "") -> dict:
        return {}


@pytest.fixture
def isolated_db(db_session):
    """Provides an isolated database session for testing."""
    return db_session


def test_unassigned_requirements_not_connected_to_first_table(isolated_db):
    """Verify requirements with no matching entity or module are NOT linked to the first table in the graph."""
    user = get_or_create_test_user(isolated_db)
    proj = Project(
        id=str(uuid.uuid4()),
        name="Logistics System",
        description="Freight tracking platform",
        user_id=user.id
    )
    isolated_db.add(proj)

    # Tables in schema
    schema_art = Artifact(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        artifact_type="schema",
        title="Database Schema",
        current_version=1,
        content_json=json.dumps({
            "tables": [
                {
                    "name": "shipments",
                    "requirement_ids": ["FR-001"],
                    "columns": [{"name": "id", "type": "INTEGER", "pk": True}]
                },
                {
                    "name": "carriers",
                    "requirement_ids": ["FR-002"],
                    "columns": [{"name": "id", "type": "INTEGER", "pk": True}]
                }
            ]
        })
    )
    isolated_db.add(schema_art)

    # Requirements: FR-001 matches shipments, FR-999 is completely unassigned
    reqs = [
        ExtractedRequirement(
            project_id=proj.id,
            req_id="FR-001",
            category="functional",
            title="Create Shipment",
            description="Allows shippers to create shipment orders."
        ),
        ExtractedRequirement(
            project_id=proj.id,
            req_id="FR-999",
            category="functional",
            title="Calculate Tax Rates",
            description="Applies state tax percentages dynamically without database persistence."
        )
    ]
    for r in reqs:
        isolated_db.add(r)
    isolated_db.commit()

    # Generate Knowledge Graph
    GraphService.generate_knowledge_graph(proj.id, isolated_db)
    graph_data = GraphService.get_graph_data(proj.id, isolated_db)

    edges = graph_data["edges"]
    matrix = graph_data["matrix"]

    # FR-999 must NOT have an edge to ENT_shipments (which was the first_tid)
    fr999_edges = [e for e in edges if e["source"] == "FR-999" or e["target"] == "FR-999"]
    assert len(fr999_edges) == 0, f"FR-999 should have 0 graph edges, found: {fr999_edges}"

    # Traceability matrix row for FR-999 must be 'unmapped'
    row_999 = next((row for row in matrix if row["requirement_id"] == "FR-999"), None)
    assert row_999 is not None
    assert row_999["coverage_status"] == "unmapped"
    assert row_999["entities"] == []
    assert row_999["apis"] == []


def test_api_endpoints_do_not_force_loose_token_mapping(isolated_db):
    """Verify that an unrelated requirement is not assigned to endpoints by keyword or token overlap."""
    user = get_or_create_test_user(isolated_db)
    proj = Project(
        id=str(uuid.uuid4()),
        name="Hotel Management System",
        description="Room reservation and guest billing",
        user_id=user.id
    )
    isolated_db.add(proj)

    reqs = [
        ExtractedRequirement(
            project_id=proj.id,
            req_id="FR-001",
            category="functional",
            title="Manage Guest Profiles",
            description="The system shall manage guest details, addresses, and loyalty status."
        ),
        ExtractedRequirement(
            project_id=proj.id,
            req_id="FR-050",
            category="functional",
            title="Manage Depreciation Calculation Algorithm",
            description="System executes an in-memory linear asset depreciation calculation once annually."
        )
    ]
    for r in reqs:
        isolated_db.add(r)
    isolated_db.commit()

    # Mock provider returning an endpoint that mentions 'Manage' and 'system'
    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {
        "endpoints": [
            {
                "path": "/api/v1/guests",
                "method": "POST",
                "summary": "Manage and create system guest records",
                "tag": "Guests",
                "requirement_ids": ["FR-001"]
            }
        ]
    }

    with patch("backend.app.services.artifact_service.get_llm_provider", return_value=mock_provider):
        api_result = ArtifactService._generate_api_documentation(proj, reqs, isolated_db)

    endpoints = api_result.get("endpoints", [])
    guest_ep = next((ep for ep in endpoints if "/guests" in ep["path"]), None)
    assert guest_ep is not None

    # FR-050 must NOT have been appended to /api/v1/guests despite sharing words like 'manage' and 'system'
    assert "FR-050" not in guest_ep.get("requirement_ids", []), "FR-050 should not be forced onto /api/v1/guests"
    assert "FR-001" in guest_ep.get("requirement_ids", [])


def test_synthetic_tables_do_not_default_to_first_fr(isolated_db):
    """Verify that synthetic tables (audit_logs, reservations) do not default to functional_reqs[0]."""
    user = get_or_create_test_user(isolated_db)
    proj = Project(
        id=str(uuid.uuid4()),
        name="School Portal",
        description="Classroom attendance and grade tracking",
        user_id=user.id
    )
    isolated_db.add(proj)

    # Requirements have no audit logging mentioned
    reqs = [
        ExtractedRequirement(
            project_id=proj.id,
            req_id="FR-001",
            category="functional",
            title="Record Attendance",
            description="Teachers record daily student attendance."
        ),
        ExtractedRequirement(
            project_id=proj.id,
            req_id="FR-002",
            category="functional",
            title="Submit Grades",
            description="Teachers submit semester final grades."
        )
    ]
    for r in reqs:
        isolated_db.add(r)
    isolated_db.commit()

    mock_provider = MagicMock()
    mock_provider.generate_json.return_value = {
        "tables": [
            {
                "name": "attendance_records",
                "requirement_ids": ["FR-001"],
                "columns": [{"name": "id", "type": "INTEGER", "pk": True}]
            }
        ]
    }

    with patch("backend.app.services.artifact_service.get_llm_provider", return_value=mock_provider):
        schema_result = ArtifactService._generate_database_schema(proj, reqs, isolated_db)

    tables = schema_result.get("tables", [])
    audit_tbl = next((t for t in tables if t["name"] == "audit_logs"), None)
    if audit_tbl:
        # Audit logs must NOT default to FR-001
        assert "FR-001" not in audit_tbl.get("requirement_ids", []), "audit_logs should not default to FR-001"
        assert len(audit_tbl.get("requirement_ids", [])) == 0


def test_traceability_matrix_status_classification(isolated_db):
    """Verify that matrix rows correctly distinguish complete, partial, and unmapped coverage statuses."""
    user = get_or_create_test_user(isolated_db)
    proj = Project(
        id=str(uuid.uuid4()),
        name="Clinic EMR",
        description="Electronic medical records",
        user_id=user.id
    )
    isolated_db.add(proj)

    # 3 functional requirements:
    # FR-001: complete (has API, entity, testcase)
    # FR-002: partial (has entity only)
    # FR-003: unmapped (has none)
    reqs = [
        ExtractedRequirement(project_id=proj.id, req_id="FR-001", category="functional", title="Patient Intake", description="Intake process"),
        ExtractedRequirement(project_id=proj.id, req_id="FR-002", category="functional", title="Archive Patient", description="Data archiving"),
        ExtractedRequirement(project_id=proj.id, req_id="FR-003", category="functional", title="Export Compliance PDF", description="Generate PDF report in memory")
    ]
    for r in reqs:
        isolated_db.add(r)

    # Schema artifact with patients table covering FR-001 and FR-002
    schema_art = Artifact(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        artifact_type="schema",
        title="Database Schema",
        current_version=1,
        content_json=json.dumps({
            "tables": [
                {"name": "patients", "requirement_ids": ["FR-001", "FR-002"], "columns": [{"name": "id", "type": "INTEGER", "pk": True}]}
            ]
        })
    )
    isolated_db.add(schema_art)

    # API artifact covering FR-001 only
    api_art = Artifact(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        artifact_type="api",
        title="API Documentation",
        current_version=1,
        content_json=json.dumps({
            "endpoints": [
                {"path": "/api/v1/patients", "method": "POST", "summary": "Create patient", "requirement_ids": ["FR-001"]}
            ]
        })
    )
    isolated_db.add(api_art)

    # Testcases artifact covering FR-001 only
    tc_art = Artifact(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        artifact_type="testcases",
        title="Test Cases",
        current_version=1,
        content_json=json.dumps({
            "cases": [
                {"test_id": "TC-001", "scenario": "Intake patient test", "type": "positive", "linked_req_id": "FR-001"}
            ]
        })
    )
    isolated_db.add(tc_art)
    isolated_db.commit()

    GraphService.generate_knowledge_graph(proj.id, isolated_db)
    graph_data = GraphService.get_graph_data(proj.id, isolated_db)
    matrix = graph_data["matrix"]

    row_001 = next(r for r in matrix if r["requirement_id"] == "FR-001")
    row_002 = next(r for r in matrix if r["requirement_id"] == "FR-002")
    row_003 = next(r for r in matrix if r["requirement_id"] == "FR-003")

    assert row_001["coverage_status"] == "complete", f"FR-001 expected complete, got {row_001['coverage_status']}"
    assert row_002["coverage_status"] == "partial", f"FR-002 expected partial, got {row_002['coverage_status']}"
    assert row_003["coverage_status"] == "unmapped", f"FR-003 expected unmapped, got {row_003['coverage_status']}"


def test_bfs_impact_analysis_isolation(isolated_db):
    """Verify that BFS impact analysis on an unmapped requirement does not leak into unrelated nodes."""
    user = get_or_create_test_user(isolated_db)
    proj = Project(
        id=str(uuid.uuid4()),
        name="Pharmacy System",
        description="Prescription and dispensing system",
        user_id=user.id
    )
    isolated_db.add(proj)

    reqs = [
        ExtractedRequirement(project_id=proj.id, req_id="FR-001", category="functional", title="Dispense Medication", description="Dispense drugs to patient"),
        ExtractedRequirement(project_id=proj.id, req_id="FR-999", category="functional", title="Display Clock Widget", description="Display UTC clock on screen")
    ]
    for r in reqs:
        isolated_db.add(r)

    schema_art = Artifact(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        artifact_type="schema",
        title="Database Schema",
        current_version=1,
        content_json=json.dumps({
            "tables": [
                {"name": "prescriptions", "requirement_ids": ["FR-001"], "columns": [{"name": "id", "type": "INTEGER", "pk": True}]}
            ]
        })
    )
    isolated_db.add(schema_art)

    api_art = Artifact(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        artifact_type="api",
        title="API Documentation",
        current_version=1,
        content_json=json.dumps({
            "endpoints": [
                {"path": "/api/v1/prescriptions", "method": "POST", "summary": "Dispense medication", "requirement_ids": ["FR-001"]}
            ]
        })
    )
    isolated_db.add(api_art)
    isolated_db.commit()

    GraphService.generate_knowledge_graph(proj.id, isolated_db)

    # Perform impact analysis on the unmapped requirement FR-999
    impact = GraphService.get_impact_analysis(proj.id, "FR-999", isolated_db)

    # FR-999 is isolated: 0 affected external nodes, 0 affected edges
    assert len(impact.affected_edges) == 0, f"Expected 0 affected edges, got {impact.affected_edges}"
    # The only affected node is FR-999 itself
    assert len(impact.affected_nodes) == 1
    assert impact.affected_nodes[0].id == "FR-999"

    # Now verify impact on FR-001 DOES include its genuinely connected artifacts
    impact_001 = GraphService.get_impact_analysis(proj.id, "FR-001", isolated_db)
    affected_ids = {n.id for n in impact_001.affected_nodes}
    assert "ENT_prescriptions" in affected_ids
    assert "API-001" in affected_ids


def test_keyword_overlap_alone_does_not_establish_confirmed_relationship(isolated_db):
    """Verify that sharing words (e.g. 'report', 'rate', 'data') does not map requirement to table without explicit IDs."""
    user = get_or_create_test_user(isolated_db)
    proj = Project(
        id=str(uuid.uuid4()),
        name="Telemetry Platform",
        description="Real-time telemetry and metrics",
        user_id=user.id
    )
    isolated_db.add(proj)

    schema_art = Artifact(
        id=str(uuid.uuid4()),
        project_id=proj.id,
        artifact_type="schema",
        title="Database Schema",
        current_version=1,
        content_json=json.dumps({
            "tables": [
                # Table 'telemetry_data' explicitly linked to FR-001
                {"name": "telemetry_data", "requirement_ids": ["FR-001"], "columns": [{"name": "id", "type": "INTEGER", "pk": True}]}
            ]
        })
    )
    isolated_db.add(schema_art)

    # FR-002 contains 'telemetry' and 'data' in its description, but is an export task not linked in requirement_ids
    reqs = [
        ExtractedRequirement(project_id=proj.id, req_id="FR-001", category="functional", title="Ingest Telemetry Data", description="Store incoming telemetry sensor data"),
        ExtractedRequirement(project_id=proj.id, req_id="FR-002", category="functional", title="Render Live Chart", description="Display live chart of telemetry data stream in browser memory")
    ]
    for r in reqs:
        isolated_db.add(r)
    isolated_db.commit()

    GraphService.generate_knowledge_graph(proj.id, isolated_db)
    graph_data = GraphService.get_graph_data(proj.id, isolated_db)
    edges = graph_data["edges"]

    # FR-001 should have persists_to edge to ENT_telemetry_data
    persists_001 = [e for e in edges if e["source"] == "FR-001" and e["target"] == "ENT_telemetry_data"]
    assert len(persists_001) == 1

    # FR-002 should NOT have persists_to edge to ENT_telemetry_data merely due to keyword overlap
    persists_002 = [e for e in edges if e["source"] == "FR-002" and e["target"] == "ENT_telemetry_data"]
    assert len(persists_002) == 0, f"FR-002 must not be linked to ENT_telemetry_data by keyword overlap: {persists_002}"
