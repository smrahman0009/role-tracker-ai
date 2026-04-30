"""Cover-letter format converters.

The agent stores letters as Markdown-flavoured plain text — paragraphs
separated by blank lines, with `**bold**` markers around the contact
header (name + email + phone). For employer apply forms we need PDF or
DOCX, since `.md` is essentially never accepted.

Two converters here, both pure-Python with no system deps:
- letter_to_pdf: uses fpdf2 (Helvetica, 11pt, 1in margins, US Letter).
- letter_to_docx: uses python-docx (Calibri, 11pt, 1in margins).

Both render `**bold**` as actual bold runs. Other Markdown is passed
through as literal text — cover letters don't typically use lists,
tables, or other rich formatting.
"""

from __future__ import annotations

import re
from io import BytesIO

from docx import Document
from docx.shared import Inches, Pt
from fpdf import FPDF


_BOLD_SPLIT = re.compile(r"(\*\*[^\n*]+?\*\*)")


def _split_bold(text: str) -> list[tuple[str, bool]]:
    """Split a paragraph into (text, is_bold) chunks for run-by-run rendering.

    Markdown `**X**` becomes a bold chunk; everything else stays plain.
    Empty chunks are filtered out.
    """
    parts: list[tuple[str, bool]] = []
    for chunk in _BOLD_SPLIT.split(text):
        if not chunk:
            continue
        if chunk.startswith("**") and chunk.endswith("**") and len(chunk) > 4:
            parts.append((chunk[2:-2], True))
        else:
            parts.append((chunk, False))
    return parts


# ----- PDF -----


def letter_to_pdf(text: str) -> bytes:
    """Render the letter text as a US-Letter PDF and return the bytes."""
    pdf = FPDF(format="Letter", unit="pt")
    pdf.set_margins(left=72, top=72, right=72)  # 1 inch margins
    pdf.set_auto_page_break(auto=True, margin=72)
    pdf.add_page()
    pdf.set_font("Helvetica", size=11)

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    line_height = 14  # ~1.27 leading at 11pt
    paragraph_gap = 8

    for i, para in enumerate(paragraphs):
        for run_text, is_bold in _split_bold(para):
            # multi_cell wraps; for inline runs we use write() so bold
            # spans flow with surrounding plain text on the same line.
            pdf.set_font("Helvetica", style="B" if is_bold else "", size=11)
            pdf.write(line_height, run_text)
        # End of paragraph — newline, then a small gap.
        pdf.ln(line_height)
        if i < len(paragraphs) - 1:
            pdf.ln(paragraph_gap)

    return bytes(pdf.output())


# ----- DOCX -----


def letter_to_docx(text: str) -> bytes:
    """Render the letter text as a .docx and return the bytes."""
    doc = Document()
    # 1 inch margins on all sides.
    for section in doc.sections:
        section.top_margin = Inches(1)
        section.bottom_margin = Inches(1)
        section.left_margin = Inches(1)
        section.right_margin = Inches(1)
    # Default style: Calibri 11pt (Word's standard).
    style = doc.styles["Normal"]
    style.font.name = "Calibri"
    style.font.size = Pt(11)

    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    for para in paragraphs:
        p = doc.add_paragraph()
        for run_text, is_bold in _split_bold(para):
            run = p.add_run(run_text)
            run.bold = is_bold

    buf = BytesIO()
    doc.save(buf)
    return buf.getvalue()
