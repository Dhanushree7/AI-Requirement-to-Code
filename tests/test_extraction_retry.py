"""
Unit and integration tests for JSON parsing retry behavior, Gemini structured-output compatibility,
MAX_TOKENS truncation detection, extraction resilience, and full-document requirement preservation.
"""

import json
import re
import pytest
from pathlib import Path
from typing import Any, Dict, Optional
from unittest.mock import patch, MagicMock
from pydantic import BaseModel, Field

from backend.app.models.project import Project, UploadedFile
from backend.app.models.requirement import ExtractedRequirement
from backend.app.schemas.domain_model import DomainModel
from backend.app.services.llm.base import BaseLLMProvider, LLMValidationError, LLMTokenLimitError
from backend.app.services.llm.gemini_provider import GeminiProvider, pydantic_to_gemini_schema
from backend.app.services.requirement_service import RequirementService
from backend.app.services.project_service import ProjectService
from tests.conftest import get_or_create_test_user


class DummySchema(BaseModel):
    name: str
    count: int = Field(gt=0)


class MockFlakyJsonProvider(BaseLLMProvider):
    """Test provider returning controlled sequences of responses."""
    def __init__(self, responses):
        self.responses = list(responses)
        self.attempts = 0
        self.prompts_received = []

    def generate_text(self, prompt: str, system_prompt: Optional[str] = None,
                      temperature: Optional[float] = None, max_tokens: Optional[int] = None) -> str:
        return ""

    def generate_json(self, prompt: str, system_prompt: Optional[str] = None,
                      schema: Optional[Dict[str, Any]] = None,
                      temperature: Optional[float] = None,
                      max_tokens: Optional[int] = None) -> Dict[str, Any]:
        self.prompts_received.append(prompt)
        if self.attempts < len(self.responses):
            resp = self.responses[self.attempts]
            self.attempts += 1
            if isinstance(resp, Exception):
                raise resp
            if isinstance(resp, str):
                from backend.app.services.llm.factory import robust_json_parse
                return robust_json_parse(resp)
            return resp
        self.attempts += 1
        raise ValueError("No more responses configured in mock provider")


class TestGeminiStructuredOutputAndTruncation:
    def test_gemini_schema_compatibility(self):
        """DomainModel converts to a valid google.generativeai.protos.Schema without unsupported protobuf fields."""
        import google.generativeai as genai
        from google.generativeai.protos import Schema
        from google.generativeai.types.generation_types import to_generation_config_dict

        gemini_schema = pydantic_to_gemini_schema(DomainModel)
        assert isinstance(gemini_schema, Schema)
        assert "requirements" in gemini_schema.properties
        assert "actors" in gemini_schema.properties
        assert "entities" in gemini_schema.properties
        assert "modules" in gemini_schema.properties
        assert "constraints" in gemini_schema.properties

        # Verify GenerationConfig normalizes without raising ValueError (e.g. unknown field: default)
        cfg = genai.GenerationConfig(response_mime_type="application/json", response_schema=gemini_schema)
        cfg_dict = to_generation_config_dict(cfg)
        assert "response_schema" in cfg_dict
        assert isinstance(cfg_dict["response_schema"], Schema)

    def test_max_tokens_truncation_detection(self):
        """When Gemini finishes with MAX_TOKENS, LLMTokenLimitError is explicitly raised with token count."""
        with patch("google.generativeai.configure"), \
             patch("google.generativeai.GenerativeModel") as mock_model_cls:

            mock_model = MagicMock()
            mock_model_cls.return_value = mock_model

            # Mock candidate stopped at MAX_TOKENS
            mock_finish_reason = MagicMock()
            mock_finish_reason.name = "MAX_TOKENS"
            mock_candidate = MagicMock()
            mock_candidate.finish_reason = mock_finish_reason

            mock_usage = MagicMock()
            mock_usage.candidates_token_count = 8192

            mock_response = MagicMock()
            mock_response.candidates = [mock_candidate]
            mock_response.usage_metadata = mock_usage
            mock_response.text = '{"summary": {"domain_name": "Incomplete string starting...'

            mock_model.generate_content.return_value = mock_response

            provider = GeminiProvider(api_key="test-key-12345", model="gemini-3.5-flash-lite")

            with pytest.raises(LLMTokenLimitError) as exc_info:
                provider.generate_json(prompt="Extract requirements", schema=DomainModel)

            assert "maximum output token limit (8192 tokens) and was truncated" in str(exc_info.value)


class TestGenerateValidatedJsonRetry:
    def test_invalid_json_first_attempt_recovers_on_retry(self):
        """Invalid JSON syntax on attempt 1 triggers retry and succeeds on attempt 2."""
        provider = MockFlakyJsonProvider([
            ValueError("Invalid JSON response: Expecting property name enclosed in double quotes: line 637 column 127 (char 28524)"),
            {"name": "Valid Output", "count": 5}
        ])

        result: DummySchema = provider.generate_validated_json(
            prompt="Generate dummy data",
            response_model=DummySchema,
            max_retries=2
        )

        assert isinstance(result, DummySchema)
        assert result.name == "Valid Output"
        assert result.count == 5
        assert provider.attempts == 2
        assert "PREVIOUS ATTEMPT FAILED" in provider.prompts_received[1]
        assert "Expecting property name enclosed in double quotes" in provider.prompts_received[1]

    def test_repeated_invalid_json_reaches_retry_limit(self):
        """Repeated malformed JSON stops strictly at max_retries and raises LLMValidationError."""
        malformed_err = ValueError("Invalid JSON response: Expecting property name enclosed in double quotes: line 637 column 127 (char 28524)")
        provider = MockFlakyJsonProvider([
            malformed_err,
            malformed_err,
            malformed_err,
            malformed_err,
        ])

        with pytest.raises(LLMValidationError) as exc_info:
            provider.generate_validated_json(
                prompt="Generate dummy data",
                response_model=DummySchema,
                max_retries=2
            )

        assert provider.attempts == 3
        assert "JSON validation/parsing failed after 3 attempts" in str(exc_info.value)
        assert "Expecting property name enclosed in double quotes" in str(exc_info.value)

    def test_valid_json_failing_schema_validation_recovers(self):
        """Valid JSON that fails Pydantic schema validation retries and succeeds when corrected."""
        provider = MockFlakyJsonProvider([
            {"name": "Missing count"},  # fails count: int (gt=0)
            {"name": "Fixed Output", "count": 10}
        ])

        result: DummySchema = provider.generate_validated_json(
            prompt="Generate dummy data",
            response_model=DummySchema,
            max_retries=2
        )

        assert result.name == "Fixed Output"
        assert result.count == 10
        assert provider.attempts == 2
        assert "PREVIOUS ATTEMPT FAILED" in provider.prompts_received[1]


class TestExtractionServiceRetryAndIdempotency:
    @pytest.fixture
    def project_with_file(self, db_session):
        user = get_or_create_test_user(db_session)
        project = Project(name="Retry Test Project", status="idle", user_id=user.id)
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        uploaded = UploadedFile(
            project_id=project.id,
            filename="requirements.txt",
            file_type="txt",
            file_size=1024,
            file_path="/tmp/requirements.txt",
            extracted_text="FR-001 The user shall login.\nFR-002 The user shall logout.\nACT-001 End User.\nENT-001 User Account."
        )
        db_session.add(uploaded)
        db_session.commit()
        return project

    def test_failed_extraction_preserves_project_and_document_and_sets_error_status(self, db_session, project_with_file):
        """Terminal extraction failure commits status='error' and preserves project/file rows."""
        with patch("backend.app.services.requirement_service.get_extraction_provider") as mock_prov_getter, \
             patch("backend.app.services.graph_service.GraphService.generate_knowledge_graph"), \
             patch("backend.app.services.rag_service.RagService.index_project_chunks"):

            mock_provider = MagicMock()
            mock_provider.generate_validated_json.side_effect = LLMValidationError(
                "JSON validation/parsing failed after 3 attempts: Expecting property name enclosed in double quotes"
            )
            mock_provider.generate_json.side_effect = ValueError(
                "Invalid JSON response: Expecting property name enclosed in double quotes"
            )
            mock_prov_getter.return_value = mock_provider

            with pytest.raises(ValueError) as exc:
                RequirementService.analyze_project_requirements(project_with_file.id, db_session)

            assert "Requirement extraction failed" in str(exc.value)

            proj = db_session.query(Project).filter_by(id=project_with_file.id).first()
            assert proj is not None
            assert proj.status == "error"

            files = db_session.query(UploadedFile).filter_by(project_id=project_with_file.id).all()
            assert len(files) == 1
            assert files[0].filename == "requirements.txt"

    def test_retry_reuses_existing_project_without_duplicate_requirements(self, db_session, project_with_file):
        """Retrying extraction reuses the project/document and prevents duplicate requirement insertion."""
        mock_domain_model = {
            "summary": {"domain_name": "Auth System", "overview": "Testing auth", "assumptions": ["None"]},
            "actors": [{"req_id": "ACT-001", "title": "End User", "description": "Human operator"}],
            "requirements": [
                {"req_id": "FR-001", "category": "functional", "title": "User Login", "description": "Shall allow user login", "priority": "high"},
                {"req_id": "FR-002", "category": "functional", "title": "User Logout", "description": "Shall allow user logout", "priority": "medium"}
            ],
            "entities": [{"req_id": "ENT-001", "name": "User Account", "description": "Stores user data"}],
            "modules": [{"req_id": "MOD-001", "name": "AuthModule", "description": "Authentication"}],
            "constraints": []
        }

        with patch("backend.app.services.requirement_service.get_extraction_provider") as mock_prov_getter, \
             patch("backend.app.services.graph_service.GraphService.generate_knowledge_graph"), \
             patch("backend.app.services.rag_service.RagService.index_project_chunks"):

            mock_provider = MagicMock()
            mock_provider.generate_validated_json.side_effect = LLMValidationError("Initial failure")
            mock_provider.generate_json.side_effect = ValueError("Initial parse error")
            mock_prov_getter.return_value = mock_provider

            with pytest.raises(ValueError):
                RequirementService.analyze_project_requirements(project_with_file.id, db_session)

            proj = db_session.query(Project).filter_by(id=project_with_file.id).first()
            assert proj.status == "error"

            # In-place Retry: Now provider returns valid data
            mock_provider.generate_validated_json.side_effect = None
            mock_validated = MagicMock()
            mock_validated.model_dump.return_value = mock_domain_model
            mock_provider.generate_validated_json.return_value = mock_validated

            summary = RequirementService.analyze_project_requirements(project_with_file.id, db_session)
            assert summary["total_extracted"] == 5
            assert summary["functional_count"] == 2

            db_session.refresh(proj)
            assert proj.status == "idle"
            assert proj.current_step == "rag_llm"

            req_count = db_session.query(ExtractedRequirement).filter_by(project_id=project_with_file.id).count()
            assert req_count == 5

            # Subsequent Retry / Re-analysis: Idempotency check - no duplicates
            summary_retry = RequirementService.analyze_project_requirements(project_with_file.id, db_session)
            assert summary_retry["total_extracted"] == 0

            req_count_after = db_session.query(ExtractedRequirement).filter_by(project_id=project_with_file.id).count()
            assert req_count_after == 5


class TestFullDocumentExtractionPreservation:
    def test_full_sample_document_preserves_every_requirement(self, db_session):
        """Full extraction on farm_marketplace_requirements.txt extracts and preserves every single source requirement without omission."""
        # Load sample document from uploads
        sample_candidates = list(Path("backend/storage/uploads").glob("*farm_marketplace_requirements.txt"))
        assert len(sample_candidates) > 0, "Sample document farm_marketplace_requirements.txt must exist in backend/storage/uploads"
        sample_path = sample_candidates[0]
        assert sample_path.exists(), "Sample document farm_marketplace_requirements.txt must exist"
        doc_text = sample_path.read_text(encoding="utf-8")

        # Discover all IDs in the sample document
        strict_id_regex = r"(?m)^[\s>*-]*([A-Za-z]+-\d+)\b|\b([A-Za-z]+-\d+):"
        expected_ids = set()
        for match in re.finditer(strict_id_regex, doc_text):
            rid = match.group(1) or match.group(2)
            if rid:
                expected_ids.add(rid)

        # Expected: 5 ACTs (ACT-001..005), 32 REQs (REQ-001..032), 8 NFRs (NFR-001..008), 4 CONs (CON-001..004) = 49 total
        assert len(expected_ids) == 49
        assert {"ACT-001", "ACT-005", "REQ-001", "REQ-032", "NFR-001", "NFR-008", "CON-001", "CON-004"}.issubset(expected_ids)

        # Create project with this full document
        user = get_or_create_test_user(db_session)
        project = Project(name="Farm Full Extraction Test", status="idle", user_id=user.id)
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        uploaded = UploadedFile(
            project_id=project.id,
            filename="farm_marketplace_requirements.txt",
            file_type="txt",
            file_size=len(doc_text.encode("utf-8")),
            file_path=str(sample_path),
            extracted_text=doc_text,
            extraction_status="completed"
        )
        db_session.add(uploaded)
        db_session.commit()

        # Build mock domain model with all 49 items
        actors = [{"req_id": f"ACT-{i:03d}", "title": f"Actor {i}", "description": f"Role {i}"} for i in range(1, 6)]
        reqs = [{"req_id": f"REQ-{i:03d}", "category": "functional", "title": f"Feature {i}", "description": f"Description {i}", "priority": "high", "module_name": "CatalogModule"} for i in range(1, 33)]
        nfrs = [{"req_id": f"NFR-{i:03d}", "category": "non_functional", "title": f"Quality {i}", "description": f"Quality description {i}", "priority": "medium", "module_name": "CatalogModule"} for i in range(1, 9)]
        cons = [{"req_id": f"CON-{i:03d}", "category": "constraint", "title": f"Constraint {i}", "description": f"Constraint rule {i}", "priority": "high"} for i in range(1, 5)]

        mock_payload = {
            "summary": {"domain_name": "Farm Marketplace", "overview": "Produce platform", "assumptions": ["Mobile access"]},
            "actors": actors,
            "requirements": reqs + nfrs,
            "entities": [{"req_id": "ENT-001", "name": "ProduceListing", "description": "Produce item"}],
            "modules": [{"req_id": "MOD-001", "name": "CatalogModule", "description": "Catalog management"}],
            "constraints": cons
        }

        with patch("backend.app.services.requirement_service.get_extraction_provider") as mock_prov_getter, \
             patch("backend.app.services.graph_service.GraphService.generate_knowledge_graph"), \
             patch("backend.app.services.rag_service.RagService.index_project_chunks"):

            mock_provider = MagicMock()
            mock_validated = MagicMock()
            mock_validated.model_dump.return_value = mock_payload
            mock_provider.generate_validated_json.return_value = mock_validated
            mock_prov_getter.return_value = mock_provider

            summary = RequirementService.analyze_project_requirements(project.id, db_session)

            # Verify all 49 source requirements plus entity and module are saved
            stored_records = db_session.query(ExtractedRequirement).filter_by(project_id=project.id).all()
            stored_ids = {r.req_id for r in stored_records}

            # Prove 100% preservation of all source IDs
            assert expected_ids.issubset(stored_ids)
            assert len(stored_records) == 51  # 49 source items + 1 entity + 1 module
            assert summary["actor_count"] == 5
            assert summary["functional_count"] == 32
            assert summary["non_functional_count"] == 8
            assert summary["constraint_count"] == 4
            assert summary["entity_count"] == 1
            assert summary["module_count"] == 1


class TestDashboardStatusReflection:
    def test_dashboard_status_reflects_error_and_success(self, db_session):
        """Dashboard pipeline steps and chips reflect 'error' on terminal failure, not remaining 'pending'."""
        user = get_or_create_test_user(db_session)
        project = Project(name="Dashboard Test Project", status="error", user_id=user.id)
        db_session.add(project)
        db_session.commit()
        db_session.refresh(project)

        uploaded = UploadedFile(
            project_id=project.id,
            filename="specs.docx",
            file_type="docx",
            file_size=2048,
            file_path="/tmp/specs.docx",
            extracted_text="Some specs"
        )
        db_session.add(uploaded)
        db_session.commit()

        # 1. Terminal Failure state
        dashboard_err = ProjectService.get_dashboard_data(db_session, project.id)
        assert dashboard_err is not None
        assert dashboard_err.project_status == "error"

        extract_step = next(s for s in dashboard_err.pipeline_steps if s.id == "extraction")
        assert extract_step.state == "error"
        assert extract_step.subtext == "Extraction failed"

        rag_step = next(s for s in dashboard_err.pipeline_steps if s.id == "rag_llm")
        assert rag_step.state == "error"

        extracted_chip = next(c for c in dashboard_err.status_chips if c.id == "extracted")
        assert extracted_chip.state == "error"
        assert extracted_chip.label == "Extraction Failed"

        # 2. After Successful Recovery
        project.status = "idle"
        project.current_step = "rag_llm"
        req = ExtractedRequirement(
            project_id=project.id,
            req_id="FR-001",
            category="functional",
            title="User Auth",
            description="Login feature"
        )
        db_session.add(req)
        db_session.commit()

        dashboard_ok = ProjectService.get_dashboard_data(db_session, project.id)
        extract_step_ok = next(s for s in dashboard_ok.pipeline_steps if s.id == "extraction")
        assert extract_step_ok.state == "done"
        assert "1 requirements" in extract_step_ok.subtext

        extracted_chip_ok = next(c for c in dashboard_ok.status_chips if c.id == "extracted")
        assert extracted_chip_ok.state == "done"
        assert extracted_chip_ok.label == "Requirements Extracted"
