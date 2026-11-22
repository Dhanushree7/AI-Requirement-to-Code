"""
Tests for Domain Model CRUD endpoints, Graph & Vector re-synchronization, and Chroma isolation.
Uses pure mocking for Chroma & LLM and isolates DB sessions so execution finishes fast.
"""
import pytest
import json
from unittest.mock import patch, MagicMock

from backend.app.models.project import Project
from backend.app.models.requirement import ExtractedRequirement
from backend.app.services.rag_service import RagService
from backend.app.schemas.rag import QueryRequest
from backend.app.routers.requirements import (
    get_domain_model,
    create_domain_model,
    update_domain_model,
    delete_domain_model
)
from tests.conftest import get_or_create_test_user


def _create_mock_project(db, name="Test Domain Project"):
    user = get_or_create_test_user(db)
    p = Project(name=name, status="idle", user_id=user.id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


class TestDomainModelEndpoints:
    @patch("backend.app.services.graph_service.GraphService.generate_knowledge_graph")
    @patch("backend.app.services.rag_service.RagService.index_project_chunks")
    def test_crud_domain_model(self, mock_rag, mock_graph, db_session):
        project = _create_mock_project(db_session, "CRUD System")

        # 1. READ empty
        res = get_domain_model(project_id=project.id, project=project, db=db_session)
        assert res == {}

        # 2. CREATE (POST)
        initial_model = {
            "summary": {"domain_name": "CRUD System", "overview": "Initial overview", "assumptions": []},
            "actors": [{"req_id": "ACT-001", "title": "Admin", "description": "System Admin"}],
            "entities": [{"req_id": "ENT-001", "name": "Item", "description": "Core entity"}],
            "business_rules": [],
            "workflows": []
        }
        res_create = create_domain_model(project_id=project.id, model_data=initial_model, project=project, db=db_session)
        assert res_create["status"] == "success"

        # 3. READ after create
        res_read = get_domain_model(project_id=project.id, project=project, db=db_session)
        assert res_read["summary"]["domain_name"] == "CRUD System"

        # 4. UPDATE (PUT)
        updated_model = dict(initial_model)
        updated_model["summary"]["overview"] = "Updated overview with new rules"
        res_update = update_domain_model(project_id=project.id, model_data=updated_model, project=project, db=db_session)
        assert res_update["status"] == "success"

        res_read2 = get_domain_model(project_id=project.id, project=project, db=db_session)
        assert res_read2["summary"]["overview"] == "Updated overview with new rules"

        # 5. DELETE
        res_del = delete_domain_model(project_id=project.id, project=project, db=db_session)
        assert res_del is None

        res_read3 = get_domain_model(project_id=project.id, project=project, db=db_session)
        assert res_read3 == {}


class TestDomainModelSync:
    def test_edit_domain_model_triggers_resync(self, db_session):
        project = _create_mock_project(db_session, "Sync System")

        model_payload = {
            "summary": {"domain_name": "Hospital Inpatient", "overview": "Hospital Care Unit", "assumptions": []},
            "actors": [{"req_id": "ACT-001", "title": "Nurse", "description": "Ward nurse"}],
            "entities": [{"req_id": "ENT-001", "name": "Patient", "description": "Inpatient"}],
            "business_rules": [],
            "workflows": []
        }

        with patch("backend.app.services.graph_service.GraphService.generate_knowledge_graph") as mock_graph, \
             patch("backend.app.services.rag_service.RagService.index_project_chunks") as mock_rag:
            res = update_domain_model(project_id=project.id, model_data=model_payload, project=project, db=db_session)
            assert res["status"] == "success"
            assert mock_graph.called
            assert mock_rag.called


class TestPerProjectChromaIsolation:
    def test_cross_project_chroma_isolation(self, db_session):
        proj_a = _create_mock_project(db_session, "Hospital Care")
        req_a = ExtractedRequirement(
            project_id=proj_a.id,
            req_id="FR-001",
            category="functional",
            title="Medical Records Tracking",
            description="Inpatient medical history and clinical diagnoses",
            priority="high",
            module_name="Clinical"
        )
        db_session.add(req_a)

        proj_b = _create_mock_project(db_session, "Public Library")
        req_b = ExtractedRequirement(
            project_id=proj_b.id,
            req_id="FR-001",
            category="functional",
            title="Book Catalog Lending",
            description="Allows patrons to checkout paperback books and borrow magazines",
            priority="high",
            module_name="Circulation"
        )
        db_session.add(req_b)
        db_session.commit()

        mock_collections = {}

        class MockCollection:
            def __init__(self, name):
                self.name = name
                self.docs = []
                self.metas = []

            def add(self, ids, documents, metadatas):
                self.docs.extend(documents)
                self.metas.extend(metadatas)

            def query(self, query_texts, n_results=4):
                q = query_texts[0].lower()
                matched_docs = [d for d in self.docs if any(w in d.lower() for w in q.split())]
                matched_metas = [m for d, m in zip(self.docs, self.metas) if any(w in d.lower() for w in q.split())]
                return {
                    "documents": [matched_docs[:n_results]],
                    "metadatas": [matched_metas[:n_results]]
                }

        mock_chroma = MagicMock()
        mock_chroma.get_collection.side_effect = lambda name: mock_collections.get(name)
        def create_coll(name):
            c = MockCollection(name)
            mock_collections[name] = c
            return c
        mock_chroma.create_collection.side_effect = create_coll
        mock_chroma.delete_collection.side_effect = lambda name: mock_collections.pop(name, None)

        with patch("backend.app.services.rag_service.chroma_client", mock_chroma):
            # Index both into their isolated collections
            RagService.index_project_chunks(proj_a.id, db_session)
            RagService.index_project_chunks(proj_b.id, db_session)

            # Query Project A (Hospital) with Library question
            query_req = QueryRequest(question="How do patrons borrow paperback books?", include_artifacts=False)
            res_a = RagService.query_project(proj_a.id, query_req, db_session)

            # Assert Project A refuses because it has zero chunks from Project B
            assert "not covered in the current project" in res_a.answer.lower()
            for citation in res_a.citations:
                assert "library" not in citation.lower()
                assert "book" not in citation.lower()
                assert "borrow" not in citation.lower()
