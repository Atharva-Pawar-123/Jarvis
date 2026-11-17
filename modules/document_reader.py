"""
modules/document_reader.py — JARVIS Document Reader
====================================================
Extracts text from PDF (PyMuPDF) and Word (.docx) files.
"""

import logging
from pathlib import Path
import io

import fitz  # PyMuPDF
from docx import Document

try:
    from PIL import Image
    import pytesseract
    HAS_OCR = True
except ImportError:
    HAS_OCR = False

logger = logging.getLogger(__name__)


class DocumentReader:
    """
    Handles reading and text extraction from various document formats.
    """

    def read_pdf(self, file_path: str) -> str:
        """
        Extract text from a PDF file with optional OCR fallback for scanned pages.
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return f"I cannot find the file at {file_path}, sir."

            text_blocks = []
            with fitz.open(str(path)) as doc:
                for page_num in range(len(doc)):
                    page = doc.load_page(page_num)
                    page_text = page.get_text().strip()
                    
                    # OCR Fallback if page is mostly images / empty text
                    if not page_text and HAS_OCR:
                        try:
                            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                            img = Image.open(io.BytesIO(pix.tobytes("png")))
                            page_text = pytesseract.image_to_string(img)
                            if page_text.strip():
                                page_text = f"[OCR Extracted]:\n{page_text}"
                        except Exception as e:
                            logger.warning(f"OCR failed on page {page_num}: {e}")
                    
                    if page_text:
                        text_blocks.append(page_text)

            text = "\n\n".join(text_blocks)
            if not text.strip():
                return "The PDF appears to be empty or contains only images (and OCR is unavailable), sir."

            return text
        except Exception as exc:
            logger.error(f"PDF extraction failed: {exc}")
            return f"I failed to read the PDF, sir. Error: {exc}"

    def read_docx(self, file_path: str) -> str:
        """
        Extract text from a Word (.docx) file.
        """
        try:
            path = Path(file_path)
            if not path.exists():
                return f"I cannot find the file at {file_path}, sir."

            doc = Document(str(path))
            text = "\n".join([para.text for para in doc.paragraphs])

            if not text.strip():
                return "The document appears to be empty, sir."

            return text
        except Exception as exc:
            logger.error(f"DOCX extraction failed: {exc}")
            return f"I failed to read the Word document, sir. Error: {exc}"

    def read(self, file_path: str) -> str:
        """
        Generic read method that dispatches based on file extension.
        """
        path = Path(file_path)
        ext = path.suffix.lower()

        if ext == ".pdf":
            return self.read_pdf(file_path)
        elif ext == ".docx":
            return self.read_docx(file_path)
        elif ext in [".txt", ".log", ".py", ".md", ".csv", ".json"]:
            try:
                return path.read_text(encoding="utf-8")
            except Exception as exc:
                return f"I could not read the text file, sir. Error: {exc}"
        else:
            return f"I do not support the {ext} file format yet, sir."

    def ingest_to_memory(self, file_path: str, memory_engine, chunk_size: int = 1200, overlap: int = 150) -> int:
        """
        Reads document, chunks text, and indexes into Semantic RAG ChromaDB.
        Returns the number of indexed chunks.
        """
        text = self.read(file_path)
        if not text or text.startswith("I cannot find") or text.startswith("I failed"):
            return 0

        chunks = self.chunk_text(text, chunk_size=chunk_size, overlap=overlap)
        indexed = 0
        file_name = Path(file_path).name

        for i, chunk in enumerate(chunks):
            try:
                meta = {
                    "source": file_name,
                    "file_path": str(file_path),
                    "chunk_index": i,
                    "total_chunks": len(chunks),
                    "category": "document"
                }
                if hasattr(memory_engine, "add_fact"):
                    memory_engine.add_fact(f"[{file_name} Part {i+1}]: {chunk}", meta)
                elif hasattr(memory_engine, "docs_col") and memory_engine.docs_col:
                    import uuid
                    memory_engine.docs_col.add(
                        documents=[chunk],
                        metadatas=[meta],
                        ids=[f"doc_{uuid.uuid4().hex[:12]}"]
                    )
                indexed += 1
            except Exception as e:
                logger.warning(f"Failed to index chunk {i} of {file_name}: {e}")

        return indexed

    def chunk_text(self, text: str, chunk_size: int = 1500, overlap: int = 200) -> list:
        """
        Advanced Semantic Chunking: Split text into overlapping windows 
        to ensure context isn't lost across chunk boundaries.
        
        Args:
            text: The text to chunk.
            chunk_size: Max characters per chunk.
            overlap: Overlap in characters to maintain context.
        """
        if not text or not text.strip():
            return []

        # Guard against infinite loop: overlap must be less than chunk_size
        if chunk_size <= 0:
            chunk_size = 1500
        if overlap < 0:
            overlap = 0
        if overlap >= chunk_size:
            overlap = chunk_size // 4  # safe default: 25% overlap

        # Split by paragraphs first to try to keep semantic boundaries
        paragraphs = text.split('\n\n')
        chunks = []
        current_chunk = ""
        
        for para in paragraphs:
            if len(current_chunk) + len(para) <= chunk_size:
                current_chunk += para + "\n\n"
            else:
                if current_chunk:
                    chunks.append(current_chunk.strip())
                # If a single paragraph is larger than chunk_size, we fall back to hard slicing
                if len(para) > chunk_size:
                    start = 0
                    while start < len(para):
                        end = min(start + chunk_size, len(para))
                        chunks.append(para[start:end])
                        start += (chunk_size - overlap)
                    current_chunk = chunks.pop() if chunks else ""
                else:
                    current_chunk = para + "\n\n"
                    
        if current_chunk:
            chunks.append(current_chunk.strip())
            
        return chunks
