"""PDF text extraction, OCR fallback, and citation-ready chunk generation.

Original documents remain authoritative. This module creates derived JSON only;
it never changes a source PDF. OCR is attempted only for low-text PDFs and only
when the ``ocrmypdf`` executable is available in the running environment.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path

PROCESSOR_VERSION = "legal-pdf-v1"
MIN_NATIVE_TEXT_CHARACTERS = 40


@dataclass(frozen=True)
class PageText:
    page: int
    text: str


@dataclass(frozen=True)
class CitationChunk:
    chunk_id: str
    text: str
    page_start: int
    page_end: int
    char_start: int
    char_end: int


@dataclass(frozen=True)
class ProcessedDocument:
    schema_version: str
    processor_version: str
    source_sha256: str
    source_pdf_key: str
    created_at: str
    extraction_method: str
    ocr_status: str
    ocr_languages: str
    page_count: int
    pages: list[PageText]
    chunks: list[CitationChunk]

    def to_bytes(self) -> bytes:
        return (
            json.dumps(asdict(self), ensure_ascii=False, indent=2, sort_keys=True)
            + "\n"
        ).encode("utf-8")


def _normalise_text(text: str) -> str:
    lines = [" ".join(line.split()) for line in text.replace("\r", "\n").split("\n")]
    return "\n".join(line for line in lines if line).strip()


def extract_native_pages(pdf_bytes: bytes) -> list[PageText]:
    """Extract selectable PDF text while keeping the original PDF page numbers."""

    try:
        import fitz
    except ImportError as error:  # pragma: no cover - environment configuration
        raise RuntimeError("PyMuPDF is required; install the production dependencies") from error

    try:
        document = fitz.open(stream=pdf_bytes, filetype="pdf")
    except Exception as error:
        raise ValueError("Could not open downloaded PDF for text extraction") from error

    try:
        return [PageText(page=index + 1, text=_normalise_text(page.get_text("text"))) for index, page in enumerate(document)]
    finally:
        document.close()


def _requires_ocr(pages: list[PageText]) -> bool:
    return bool(pages) and any(len(page.text) < MIN_NATIVE_TEXT_CHARACTERS for page in pages)


def _ocr_pdf(pdf_bytes: bytes, *, languages: str) -> bytes:
    executable = shutil.which("ocrmypdf")
    if not executable:
        raise FileNotFoundError("ocrmypdf executable is not installed")

    with tempfile.TemporaryDirectory(prefix="legalai-ocr-") as directory:
        input_path = Path(directory) / "source.pdf"
        output_path = Path(directory) / "searchable.pdf"
        input_path.write_bytes(pdf_bytes)
        command = [
            executable,
            "--skip-text",
            "--output-type",
            "pdf",
            "--language",
            languages,
            str(input_path),
            str(output_path),
        ]
        completed = subprocess.run(command, capture_output=True, text=True, timeout=900, check=False)
        if completed.returncode != 0 or not output_path.exists():
            detail = (completed.stderr or completed.stdout).strip()[-1000:]
            raise RuntimeError(f"OCR failed: {detail or 'ocrmypdf exited unsuccessfully'}")
        return output_path.read_bytes()


def _chunks_for_page(page: PageText, *, size: int, overlap: int) -> list[CitationChunk]:
    chunks: list[CitationChunk] = []
    text = page.text
    start = 0
    sequence = 1
    while start < len(text):
        end = min(len(text), start + size)
        if end < len(text):
            boundary = text.rfind(" ", start, end)
            if boundary > start:
                end = boundary
        part = text[start:end].strip()
        if part:
            left_trimmed = len(text[start:end]) - len(text[start:end].lstrip())
            chunks.append(
                CitationChunk(
                    chunk_id=f"p{page.page:04d}-c{sequence:03d}",
                    text=part,
                    page_start=page.page,
                    page_end=page.page,
                    char_start=start + left_trimmed,
                    char_end=start + left_trimmed + len(part),
                )
            )
            sequence += 1
        if end >= len(text):
            break
        desired_start = max(end - overlap, start + 1)
        # Keep overlap where possible, but never start in the middle of a
        # word. If there is no earlier word boundary, advance to the next one.
        overlap_boundary = text.rfind(" ", start + 1, desired_start + 1)
        if overlap_boundary >= 0:
            start = overlap_boundary + 1
        else:
            next_boundary = text.find(" ", desired_start)
            start = next_boundary + 1 if next_boundary >= 0 else desired_start
    return chunks


def build_citation_chunks(
    pages: list[PageText], *, size: int = 1_600, overlap: int = 250
) -> list[CitationChunk]:
    """Chunk per page so every retrieval result has an exact source page."""

    if size <= 0 or overlap < 0 or overlap >= size:
        raise ValueError("chunk size must be positive and overlap must be smaller than size")
    return [chunk for page in pages for chunk in _chunks_for_page(page, size=size, overlap=overlap)]


def process_pdf(
    pdf_bytes: bytes,
    *,
    source_sha256: str,
    source_pdf_key: str,
    ocr_languages: str = "eng+sin+tam",
) -> ProcessedDocument:
    """Create a derived artifact using native text and OCR only when necessary."""

    pages = extract_native_pages(pdf_bytes)
    extraction_method = "native"
    ocr_status = "not_needed"
    if _requires_ocr(pages):
        try:
            pages = extract_native_pages(_ocr_pdf(pdf_bytes, languages=ocr_languages))
            extraction_method = "ocr"
            ocr_status = "completed"
        except FileNotFoundError:
            ocr_status = "required_but_unavailable"
        except Exception as error:
            ocr_status = f"failed: {str(error)[:500]}"

    return ProcessedDocument(
        schema_version="1",
        processor_version=PROCESSOR_VERSION,
        source_sha256=source_sha256,
        source_pdf_key=source_pdf_key,
        created_at=datetime.now(timezone.utc).isoformat(),
        extraction_method=extraction_method,
        ocr_status=ocr_status,
        ocr_languages=ocr_languages,
        page_count=len(pages),
        pages=pages,
        chunks=build_citation_chunks(pages),
    )
