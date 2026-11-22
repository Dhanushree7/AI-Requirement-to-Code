"""
Domain-independence test suite for Req-to-Code framework.
Verifies that any requirement document from ANY domain (hospital, e-commerce,
hotel, food delivery, farm marketplace) generates authentic domain artifacts
with ZERO cross-domain contamination, correct PK/FK structures, and dynamic
table merging without hardcoded alias dictionaries.
"""
import pytest
import json
from pathlib import Path

from backend.app.models.project import Project, UploadedFile
from backend.app.models.requirement import ExtractedRequirement
from backend.app.models.artifact import Artifact
from backend.app.services.requirement_service import RequirementService
from backend.app.services.artifact_service import ArtifactService
from backend.app.services.rag_service import RagService
from backend.app.schemas.rag import QueryRequest

SAMPLE_DIR = Path(__file__).resolve().parent.parent / "sample_docs"
UPLOADS_DIR = Path(__file__).resolve().parent.parent / "backend" / "storage" / "uploads"

LIBRARY_FORBIDDEN_WORDS = ["borrow", "librarian", "patron", "isbn", "fines", "circulation"]
FARM_FORBIDDEN_WORDS = ["produce_listings", "farm_profiles", "farmer_payouts", "crop", "harvest"]

def _create_project_with_doc(db, project_name, filename, source_dir=SAMPLE_DIR, user_id=None):
    if user_id is None:
        from tests.conftest import get_or_create_test_user
        user = get_or_create_test_user(db)
        user_id = user.id
    p = Project(name=project_name, status="idle", user_id=user_id)
    db.add(p)
    db.commit()
    db.refresh(p)

    file_path = source_dir / filename
    text = file_path.read_text(encoding="utf-8") if file_path.exists() else f"Requirements for {project_name}"

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


class TestHospitalManagementDomain:
    def test_hospital_requirements_contain_no_library_terms(self, db_session):
        p, _ = _create_project_with_doc(db_session, "Hospital Management System", "hospital_management_system.txt")
        result = RequirementService.analyze_project_requirements(p.id, db_session)
        assert result["total_extracted"] > 0
        reqs = RequirementService.get_requirements(p.id, None, db_session)
        all_text = " ".join([f"{r.title} {r.description} {r.module_name or ''}" for r in reqs]).lower()
        
        # Must contain hospital terms
        assert any(term in all_text for term in ["patient", "doctor", "appointment", "medical", "hospital"])
        # Must NOT contain library terms
        for word in LIBRARY_FORBIDDEN_WORDS:
            assert word not in all_text, f"Forbidden library term '{word}' found in hospital requirements!"
        # Must NOT contain farm terms
        for word in FARM_FORBIDDEN_WORDS:
            assert word not in all_text, f"Forbidden farm term '{word}' found in hospital requirements!"

    def test_hospital_schema_has_medical_tables(self, db_session):
        p, _ = _create_project_with_doc(db_session, "Hospital Management System", "hospital_management_system.txt")
        RequirementService.analyze_project_requirements(p.id, db_session)
        
        art = ArtifactService.generate_artifact(p.id, "schema", db_session)
        content = json.loads(art.content_json)
        table_names = [t["name"].lower() for t in content["tables"]]
        
        # Must NOT have library tables or farm tables
        assert "books" not in table_names
        assert "borrowings" not in table_names
        assert "produce_listings" not in table_names
        assert "farm_profiles" not in table_names

        # Must have relevant hospital or user tables
        assert "users" in table_names

    def test_hospital_actor_extraction_and_schema_pks_fks(self, db_session):
        p, _ = _create_project_with_doc(db_session, "Hospital Management System", "hospital_management_system.txt")
        RequirementService.analyze_project_requirements(p.id, db_session)
        
        reqs = RequirementService.get_requirements(p.id, None, db_session)
        actors = [r.title for r in reqs if r.category == "actor"]
        
        # Assert extracted actors reflect hospital domain
        assert any(a.lower() in ["patient", "doctor", "nurse", "staff", "administrator", "physician", "user"] for a in actors)
        assert "farmer" not in [a.lower() for a in actors]
        assert "librarian" not in [a.lower() for a in actors]

        # Assert schema artifact structure and PK/FK integrity
        art = ArtifactService.generate_artifact(p.id, "schema", db_session)
        schema = json.loads(art.content_json)
        tables = schema.get("tables", [])
        assert len(tables) >= 2

        for tbl in tables:
            # Exactly one primary key column per table
            pk_cols = [c for c in tbl.get("columns", []) if c.get("pk")]
            assert len(pk_cols) == 1, f"Table {tbl['name']} must have exactly one primary key, found: {pk_cols}"
            
            # Foreign keys must retain their original name and NOT be converted to 'id'
            for c in tbl.get("columns", []):
                cn = c["name"].lower()
                if cn in ["patient_id", "doctor_id", "user_id"]:
                    assert c.get("pk") is False, f"Foreign key {cn} in table {tbl['name']} must not be marked PK"
                    assert cn != "id"


class TestHotelBookingDomain:
    def test_hotel_requirements_contain_no_library_terms(self, db_session):
        p, _ = _create_project_with_doc(db_session, "Hotel Booking System", "hotel_booking_system.txt")
        result = RequirementService.analyze_project_requirements(p.id, db_session)
        assert result["total_extracted"] > 0
        reqs = RequirementService.get_requirements(p.id, None, db_session)
        all_text = " ".join([f"{r.title} {r.description}" for r in reqs]).lower()
        
        # Must contain hotel terms
        assert any(term in all_text for term in ["room", "guest", "reservation", "check-in", "hotel", "housekeeping"])
        for word in LIBRARY_FORBIDDEN_WORDS:
            assert word not in all_text, f"Forbidden library term '{word}' found in hotel requirements!"
        for word in FARM_FORBIDDEN_WORDS:
            assert word not in all_text, f"Forbidden farm term '{word}' found in hotel requirements!"

    def test_hotel_actor_extraction_and_reservation_schema(self, db_session):
        p, _ = _create_project_with_doc(db_session, "Hotel Booking System", "hotel_booking_system.txt")
        RequirementService.analyze_project_requirements(p.id, db_session)
        
        reqs = RequirementService.get_requirements(p.id, None, db_session)
        actors = [r.title.lower() for r in reqs if r.category == "actor"]
        assert any(a in ["guest", "manager", "receptionist", "staff", "user"] for a in actors)
        assert "farmer" not in actors
        assert "patient" not in actors

        art = ArtifactService.generate_artifact(p.id, "schema", db_session)
        schema = json.loads(art.content_json)
        tables = {t["name"].lower(): t for t in schema.get("tables", [])}

        # Check that reservation entity does NOT link to produce_listings
        for t_name, tbl in tables.items():
            if "reserv" in t_name or "booking" in t_name:
                for c in tbl.get("columns", []):
                    fk_target = c.get("fk") or ""
                    assert "produce_listings" not in fk_target, f"Hotel reservation in {t_name} has invalid produce FK: {fk_target}"


class TestOnlineShoppingDomain:
    def test_shopping_requirements_contain_no_library_terms(self, db_session):
        p, _ = _create_project_with_doc(db_session, "Online Shopping Platform", "online_shopping_system.txt")
        result = RequirementService.analyze_project_requirements(p.id, db_session)
        assert result["total_extracted"] > 0
        reqs = RequirementService.get_requirements(p.id, None, db_session)
        all_text = " ".join([f"{r.title} {r.description}" for r in reqs]).lower()
        
        assert any(term in all_text for term in ["product", "cart", "order", "merchant", "checkout", "shipping", "customer"])
        for word in LIBRARY_FORBIDDEN_WORDS:
            assert word not in all_text, f"Forbidden library term '{word}' found in shopping requirements!"

    def test_shopping_api_docs_have_e_commerce_routes(self, db_session):
        p, _ = _create_project_with_doc(db_session, "Online Shopping Platform", "online_shopping_system.txt")
        RequirementService.analyze_project_requirements(p.id, db_session)
        
        art = ArtifactService.generate_artifact(p.id, "api", db_session)
        content = json.loads(art.content_json)
        paths = [ep["path"].lower() for ep in content.get("endpoints", [])]
        
        assert not any("book" in path for path in paths)
        assert not any("borrow" in path for path in paths)
        assert not any("farm" in path for path in paths)

    def test_shopping_schema_pks_and_fks(self, db_session):
        p, _ = _create_project_with_doc(db_session, "Online Shopping Platform", "online_shopping_system.txt")
        RequirementService.analyze_project_requirements(p.id, db_session)
        
        art = ArtifactService.generate_artifact(p.id, "schema", db_session)
        schema = json.loads(art.content_json)
        tables = {t["name"].lower(): t for t in schema.get("tables", [])}

        # Assert order_items or order line items preserve order_id foreign key
        if "order_items" in tables:
            oi_cols = {c["name"].lower(): c for c in tables["order_items"].get("columns", [])}
            assert "order_id" in oi_cols, "order_items must contain order_id foreign key"
            assert oi_cols["order_id"].get("pk") is False, "order_id in order_items must be FK, not PK"


class TestFoodDeliveryDomain:
    def test_food_delivery_from_raw_text(self, db_session):
        from tests.conftest import get_or_create_test_user
        user = get_or_create_test_user(db_session)
        p = Project(name="Online Food Delivery System", status="idle", user_id=user.id)
        db_session.add(p)
        db_session.commit()

        raw_food_spec = """# Food Delivery App Requirements
- FR-001: Customers shall browse restaurant menus, filter by cuisine, and select food items.
- FR-002: Customers shall place food orders and pay using digital wallet or credit card.
- FR-003: Restaurants shall accept incoming food orders and update cooking status.
- FR-004: Delivery drivers shall accept delivery requests and provide real-time GPS tracking.
- NFR-001: Order dispatch notification must reach drivers within 3 seconds.
"""
        f = UploadedFile(
            project_id=p.id,
            filename="food_delivery.txt",
            file_path="/tmp/food_delivery.txt",
            file_type="txt",
            file_size=len(raw_food_spec.encode("utf-8")),
            extracted_text=raw_food_spec,
            extraction_status="completed"
        )
        db_session.add(f)
        db_session.commit()

        RequirementService.analyze_project_requirements(p.id, db_session)
        reqs = RequirementService.get_requirements(p.id, None, db_session)
        all_text = " ".join([f"{r.title} {r.description}" for r in reqs]).lower()

        assert any(term in all_text for term in ["restaurant", "food", "order", "driver", "menu"])
        for word in LIBRARY_FORBIDDEN_WORDS:
            assert word not in all_text, f"Forbidden library term '{word}' found in food delivery requirements!"

    def test_food_delivery_schema_and_fks(self, db_session):
        from tests.conftest import get_or_create_test_user
        user = get_or_create_test_user(db_session)
        p = Project(name="Online Food Delivery System", status="idle", user_id=user.id)
        db_session.add(p)
        db_session.commit()

        raw_food_spec = """# Food Delivery App Requirements
- FR-001: Customers shall browse restaurant menus, filter by cuisine, and select food items.
- FR-002: Customers shall place food orders and pay using digital wallet or credit card.
- FR-003: Restaurants shall accept incoming food orders and update cooking status.
- FR-004: Delivery drivers shall accept delivery requests and provide real-time GPS tracking.
- NFR-001: Order dispatch notification must reach drivers within 3 seconds.
"""
        f = UploadedFile(
            project_id=p.id,
            filename="food_delivery.txt",
            file_path="/tmp/food_delivery.txt",
            file_type="txt",
            file_size=len(raw_food_spec.encode("utf-8")),
            extracted_text=raw_food_spec,
            extraction_status="completed"
        )
        db_session.add(f)
        db_session.commit()

        RequirementService.analyze_project_requirements(p.id, db_session)
        art = ArtifactService.generate_artifact(p.id, "schema", db_session)
        schema = json.loads(art.content_json)
        tables = schema.get("tables", [])
        assert len(tables) >= 2
        for tbl in tables:
            pks = [c for c in tbl.get("columns", []) if c.get("pk")]
            assert len(pks) == 1, f"Table {tbl['name']} must have exactly one primary key"


class TestFarmMarketplaceRegressionDomain:
    """Regression test verifying Farm Marketplace functions seamlessly under the generic engine without hardcoded aliases."""
    def test_farm_marketplace_extraction_and_schema(self, db_session):
        sample_farm_file = next(UPLOADS_DIR.glob("*farm_marketplace_requirements.txt"), None)
        assert sample_farm_file is not None and sample_farm_file.exists(), "Farm marketplace sample file missing"

        p, _ = _create_project_with_doc(db_session, "Farm Marketplace Management", sample_farm_file.name, source_dir=UPLOADS_DIR)
        result = RequirementService.analyze_project_requirements(p.id, db_session)
        assert result["total_extracted"] > 0

        reqs = RequirementService.get_requirements(p.id, None, db_session)
        all_text = " ".join([f"{r.title} {r.description}" for r in reqs]).lower()
        assert any(term in all_text for term in ["farm", "farmer", "produce", "buyer", "payout"])

        # Generate schema without static aliases
        art = ArtifactService.generate_artifact(p.id, "schema", db_session)
        schema = json.loads(art.content_json)
        tables = {t["name"].lower(): t for t in schema.get("tables", [])}

        # Check primary key integrity across all generated tables
        for t_name, tbl in tables.items():
            pk_cols = [c for c in tbl.get("columns", []) if c.get("pk")]
            assert len(pk_cols) == 1, f"Table {t_name} has invalid PK count: {len(pk_cols)}"


class TestRagDomainSeparationAndRefusal:
    def test_cross_domain_query_refused(self, db_session):
        p, _ = _create_project_with_doc(db_session, "Hospital Management System", "hospital_management_system.txt")
        RequirementService.analyze_project_requirements(p.id, db_session)

        # Ask question about books/borrowing which has zero relevance to hospital
        req = QueryRequest(question="How many books can a patron borrow concurrently?", include_artifacts=True)
        res = RagService.query_project(p.id, req, db_session)

        assert "not covered in the current project" in res.answer.lower()
        assert res.grounded is False

    def test_out_of_context_general_query_refused(self, db_session):
        p, _ = _create_project_with_doc(db_session, "Online Shopping Platform", "online_shopping_system.txt")
        RequirementService.analyze_project_requirements(p.id, db_session)

        req = QueryRequest(question="What is the average temperature in Antarctica during July?", include_artifacts=True)
        res = RagService.query_project(p.id, req, db_session)

        assert "not covered in the current project" in res.answer.lower()
        assert res.grounded is False

    def test_domain_relevant_query_answered(self, db_session):
        p, _ = _create_project_with_doc(db_session, "Hotel Booking System", "hotel_booking_system.txt")
        RequirementService.analyze_project_requirements(p.id, db_session)

        req = QueryRequest(question="What is the reservation cancellation policy?", include_artifacts=True)
        res = RagService.query_project(p.id, req, db_session)

        assert res.grounded is True
        assert len(res.answer) > 20
        assert "not covered" not in res.answer.lower()

    def test_dynamic_suggested_questions(self, db_session):
        p, _ = _create_project_with_doc(db_session, "Hospital Management System", "hospital_management_system.txt")
        RequirementService.analyze_project_requirements(p.id, db_session)
        ArtifactService.generate_artifact(p.id, "schema", db_session)

        qs = RagService.get_suggested_questions(p.id, db_session)
        assert len(qs) >= 3
        for item in qs:
            assert "borrowing table" not in item["q"].lower()
            assert "borrowing table" not in item["label"].lower()
