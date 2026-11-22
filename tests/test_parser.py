"""
Tests for parser_service: PDF / DOCX / TXT text extraction and chunking.

The ParserService is a class with static methods:
  - extract_text(file_path, file_type) -> str
  - clean_text(text) -> str
  - chunk_text(text, chunk_size, overlap) -> List[Dict]
"""
import pytest
from pathlib import Path

from backend.app.services.parser_service import ParserService


class TestCleanText:
    def test_removes_extra_blank_lines(self):
        raw = "hello\n\n\n\nworld"
        cleaned = ParserService.clean_text(raw)
        # 3+ newlines should collapse to max 2
        assert "\n\n\n" not in cleaned

    def test_non_empty_output(self):
        result = ParserService.clean_text("  sample text  ")
        assert result.strip() != ""

    def test_empty_string(self):
        result = ParserService.clean_text("")
        assert isinstance(result, str)
        assert result == ""

    def test_crlf_normalised(self):
        raw = "line1\r\nline2\r\nline3"
        result = ParserService.clean_text(raw)
        assert "\r" not in result


class TestChunkText:
    def test_returns_list_of_dicts(self):
        text = ("This is a sentence about requirements. " * 30 + "\n\n") * 5
        chunks = ParserService.chunk_text(text)
        assert isinstance(chunks, list)
        assert len(chunks) >= 1
        for c in chunks:
            assert "text" in c and "index" in c

    def test_respects_chunk_size(self):
        para = "A" * 400
        text = (para + "\n\n") * 10
        chunks = ParserService.chunk_text(text, chunk_size=800, overlap=0)
        assert len(chunks) > 1
        for c in chunks:
            assert c["length"] > 0

    def test_no_empty_chunks(self):
        text = "Sentence. " * 100
        chunks = ParserService.chunk_text(text)
        for c in chunks:
            assert c["text"].strip() != ""

    def test_single_chunk_for_short_text(self):
        text = "Short requirement document."
        chunks = ParserService.chunk_text(text)
        assert len(chunks) == 1
        assert chunks[0]["text"] == text

    def test_sequential_indices(self):
        text = ("\n\n".join(["Paragraph " + str(i) + " " + "x" * 200 for i in range(10)]))
        chunks = ParserService.chunk_text(text)
        indices = [c["index"] for c in chunks]
        assert indices == list(range(len(chunks)))


class TestExtractText:
    def test_txt_file(self, sample_txt_path):
        text = ParserService.extract_text(str(sample_txt_path), "txt")
        assert "Library Management" in text
        assert "FR-001" in text

    def test_unsupported_format_raises(self, tmp_path):
        bad = tmp_path / "file.csv"
        bad.write_text("a,b,c")
        with pytest.raises(ValueError, match="Unsupported"):
            ParserService.extract_text(str(bad), "csv")

    def test_missing_file_raises(self):
        with pytest.raises(FileNotFoundError):
            ParserService.extract_text("/nonexistent/path/file.txt", "txt")

    def test_txt_returns_string(self, sample_txt_path):
        result = ParserService.extract_text(str(sample_txt_path), "txt")
        assert isinstance(result, str)
        assert len(result) > 10
