"""Extract plain text from a resume PDF."""

from pathlib import Path

from pypdf import PdfReader


def parse_resume(path: Path) -> str:
    """Read a PDF and return its text content joined by blank lines."""
    reader = PdfReader(str(path))
    pages = [page.extract_text() or "" for page in reader.pages]
    text = "\n\n".join(p.strip() for p in pages if p.strip())
    if not text:
        raise ValueError(
            f"No text extracted from {path}. "
            "Is the PDF a scan? pypdf cannot OCR image-only PDFs."
        )
    return text
