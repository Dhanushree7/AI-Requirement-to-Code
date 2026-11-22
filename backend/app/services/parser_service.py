import os
import re
from pathlib import Path
from typing import Tuple, List, Dict, Any
import fitz  # PyMuPDF
import docx

class ParserService:
    @staticmethod
    def extract_text(file_path: str, file_type: str) -> str:
        """Extract clean text from PDF, DOCX, or TXT file."""
        ext = file_type.lower().replace(".", "")
        path = Path(file_path)

        if not path.exists():
            raise FileNotFoundError(f"File not found: {file_path}")

        extracted_text = ""
        if ext == "pdf":
            extracted_text = ParserService._extract_pdf(path)
        elif ext in ["docx", "doc"]:
            extracted_text = ParserService._extract_docx(path)
        elif ext in ["txt", "md"]:
            extracted_text = ParserService._extract_txt(path)
        else:
            raise ValueError(f"Unsupported file type: {file_type}")

        return ParserService.clean_text(extracted_text)

    @staticmethod
    def _extract_pdf(path: Path) -> str:
        text_parts = []
        with fitz.open(str(path)) as doc:
            for page_num in range(len(doc)):
                page = doc[page_num]
                text = page.get_text()
                if text.strip():
                    text_parts.append(f"--- Page {page_num + 1} ---\n" + text.strip())
        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_docx(path: Path) -> str:
        doc = docx.Document(str(path))
        text_parts = []
        for para in doc.paragraphs:
            if para.text.strip():
                text_parts.append(para.text.strip())
        for table in doc.tables:
            table_rows = []
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells]
                table_rows.append(" | ".join(cells))
            if table_rows:
                text_parts.append("\n".join(table_rows))
        return "\n\n".join(text_parts)

    @staticmethod
    def _extract_txt(path: Path) -> str:
        with open(str(path), "r", encoding="utf-8", errors="ignore") as f:
            return f.read()

    @staticmethod
    def clean_text(text: str) -> str:
        """Normalize line breaks and excessive whitespace while preserving structure."""
        text = text.replace("\r\n", "\n").replace("\r", "\n")
        # Collapse 3 or more consecutive newlines into 2
        text = re.sub(r"\n{3,}", "\n\n", text)
        return text.strip()

    @staticmethod
    def chunk_text(text: str, chunk_size: int = 800, overlap: int = 150) -> List[Dict[str, Any]]:
        """Split document into semantic paragraphs/chunks with overlap for RAG."""
        paragraphs = text.split("\n\n")
        chunks = []
        current_chunk = ""
        current_index = 0

        for para in paragraphs:
            para = para.strip()
            if not para:
                continue

            if len(current_chunk) + len(para) <= chunk_size:
                current_chunk = (current_chunk + "\n\n" + para).strip()
            else:
                if current_chunk:
                    chunks.append({
                        "index": current_index,
                        "text": current_chunk,
                        "length": len(current_chunk)
                    })
                    current_index += 1
                    # Keep overlap from the end of current_chunk
                    current_chunk = current_chunk[-overlap:] + "\n\n" + para
                else:
                    # Paragraph itself is larger than chunk_size
                    chunks.append({
                        "index": current_index,
                        "text": para[:chunk_size],
                        "length": chunk_size
                    })
                    current_index += 1
                    current_chunk = para[chunk_size - overlap:]

        if current_chunk.strip():
            chunks.append({
                "index": current_index,
                "text": current_chunk.strip(),
                "length": len(current_chunk.strip())
            })

        return chunks
