"""
Tests for RagService: query pipeline with fallback to keyword matching.
"""
import pytest
from backend.app.models.project import Project, UploadedFile
from backend.app.models.rag_chunk import DocumentChunk
from backend.app.schemas.rag import QueryRequest
from backend.app.services.rag_service import RagService
from tests.conftest import get_or_create_test_user


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_project(db, name="RAG Test Project"):
    user = get_or_create_test_user(db)
    p = Project(name=name, status="idle", user_id=user.id)
    db.add(p)
    db.commit()
    db.refresh(p)
    return p


def _add_chunks(db, project_id, texts):
    for i, text in enumerate(texts):
        chunk = DocumentChunk(
            project_id=project_id,
            source_file="sample.txt",
            chunk_index=i,
            chunk_text=text,
        )
        db.add(chunk)
    db.commit()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------

class TestRagServiceQuery:
    def test_returns_query_response(self, db_session):
        p = _make_project(db_session)
        _add_chunks(db_session, p.id, [
            "The system shall allow registered members to borrow books for up to 14 days.",
            "Authentication is handled via JWT tokens for all protected routes.",
            "The Borrowing table stores member_id, book_id, borrow_date, and return_date.",
        ])

        req = QueryRequest(question="What is the borrowing duration?", include_artifacts=False)
        response = RagService.query_project(p.id, req, db_session)

        assert response.question == "What is the borrowing duration?"
        assert isinstance(response.answer, str)
        assert len(response.answer) > 10

    def test_grounded_true_when_chunks_exist(self, db_session):
        p = _make_project(db_session)
        _add_chunks(db_session, p.id, [
            "Non-functional requirement: system must respond within 2 seconds.",
        ])

        req = QueryRequest(question="What are the non-functional requirements?", include_artifacts=False)
        response = RagService.query_project(p.id, req, db_session)

        assert response.grounded is True

    def test_empty_question_raises(self, db_session):
        p = _make_project(db_session)
        req = QueryRequest(question="   ", include_artifacts=False)
        with pytest.raises(ValueError, match="Empty question"):
            RagService.query_project(p.id, req, db_session)

    def test_citations_are_returned(self, db_session):
        p = _make_project(db_session)
        _add_chunks(db_session, p.id, [
            "Authentication method: JWT bearer tokens issued on login.",
        ])

        req = QueryRequest(question="What authentication method is required?", include_artifacts=False)
        response = RagService.query_project(p.id, req, db_session)

        # Either a citation list or grounded result
        assert isinstance(response.citations, list)

    def test_no_chunks_returns_response_not_exception(self, db_session):
        """Project with no document chunks should return a valid (possibly ungrounded) response."""
        p = _make_project(db_session)
        req = QueryRequest(question="what is the system?", include_artifacts=False)
        # Should not raise
        response = RagService.query_project(p.id, req, db_session)
        assert response is not None
        assert isinstance(response.answer, str)

    def test_keyword_fallback_scores_relevant_chunks(self, db_session):
        p = _make_project(db_session)
        _add_chunks(db_session, p.id, [
            "Users can search for books by title, author, or ISBN.",
            "The weather today is sunny and warm.",  # irrelevant
            "Members are notified via email when a reserved book becomes available.",
        ])

        req = QueryRequest(question="How can users search for books?", include_artifacts=False)
        response = RagService.query_project(p.id, req, db_session)

        # The answer should be grounded (found a relevant chunk)
        assert response.grounded is True


class TestRagIndexChunks:
    def test_index_does_not_raise_without_chromadb(self, db_session):
        """Index should silently succeed even if ChromaDB is not available."""
        p = _make_project(db_session)
        _add_chunks(db_session, p.id, ["Sample text for indexing."])
        # Should not raise regardless of ChromaDB availability
        RagService.index_project_chunks(p.id, db_session)
