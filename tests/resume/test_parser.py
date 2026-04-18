"""Unit tests for the PDF resume parser."""

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from role_tracker.resume.parser import parse_resume


def _fake_reader(pages_text: list[str]) -> MagicMock:
    reader = MagicMock()
    reader.pages = [
        MagicMock(extract_text=MagicMock(return_value=t)) for t in pages_text
    ]
    return reader


def test_parse_resume_joins_pages_with_blank_lines() -> None:
    with patch("role_tracker.resume.parser.PdfReader") as reader_cls:
        reader_cls.return_value = _fake_reader(["Page one text.", "Page two text."])
        text = parse_resume(Path("/fake/path.pdf"))
    assert "Page one text." in text
    assert "Page two text." in text
    assert "\n\n" in text


def test_parse_resume_skips_empty_pages() -> None:
    with patch("role_tracker.resume.parser.PdfReader") as reader_cls:
        reader_cls.return_value = _fake_reader(["Real content.", "", "  "])
        text = parse_resume(Path("/fake/path.pdf"))
    assert text == "Real content."


def test_parse_resume_raises_when_all_pages_empty() -> None:
    with patch("role_tracker.resume.parser.PdfReader") as reader_cls:
        reader_cls.return_value = _fake_reader(["", "  ", ""])
        with pytest.raises(ValueError, match="No text extracted"):
            parse_resume(Path("/fake/path.pdf"))
