"""Tests for the file-backed resume store."""

import json
from pathlib import Path

import pytest

from role_tracker.resume.store import FileResumeStore

# Minimal valid PDF header — pypdf accepts more, but %PDF- is enough for sniffing.
_FAKE_PDF = b"%PDF-1.4\n% fake content\n%%EOF\n"


@pytest.fixture
def store(tmp_path: Path) -> FileResumeStore:
    return FileResumeStore(root=tmp_path / "resumes")


def test_no_metadata_when_nothing_uploaded(store: FileResumeStore) -> None:
    assert store.get_metadata("alice") is None
    assert store.get_file_bytes("alice") is None


def test_save_writes_pdf_and_meta_files(
    store: FileResumeStore, tmp_path: Path
) -> None:
    store.save_resume("alice", content=_FAKE_PDF, filename="My_Resume.pdf")
    assert (tmp_path / "resumes" / "alice.pdf").read_bytes() == _FAKE_PDF
    meta = json.loads((tmp_path / "resumes" / "alice.meta.json").read_text())
    assert meta["filename"] == "My_Resume.pdf"
    assert "uploaded_at" in meta


def test_save_returns_metadata(store: FileResumeStore) -> None:
    metadata = store.save_resume(
        "alice", content=_FAKE_PDF, filename="Resume_Final.pdf"
    )
    assert metadata.filename == "Resume_Final.pdf"
    assert metadata.size_bytes == len(_FAKE_PDF)
    assert metadata.sha256
    # SHA-256 is 64 hex chars
    assert len(metadata.sha256) == 64


def test_get_metadata_after_save(store: FileResumeStore) -> None:
    saved = store.save_resume("alice", content=_FAKE_PDF, filename="r.pdf")
    fetched = store.get_metadata("alice")
    assert fetched is not None
    assert fetched.filename == "r.pdf"
    assert fetched.sha256 == saved.sha256


def test_get_file_bytes_returns_pdf(store: FileResumeStore) -> None:
    store.save_resume("alice", content=_FAKE_PDF, filename="r.pdf")
    assert store.get_file_bytes("alice") == _FAKE_PDF


def test_save_replaces_previous(store: FileResumeStore) -> None:
    store.save_resume("alice", content=b"%PDF-1.4 first", filename="first.pdf")
    store.save_resume("alice", content=b"%PDF-1.4 second", filename="second.pdf")
    metadata = store.get_metadata("alice")
    assert metadata is not None
    assert metadata.filename == "second.pdf"
    assert store.get_file_bytes("alice") == b"%PDF-1.4 second"


def test_metadata_when_pdf_exists_without_meta_file(
    store: FileResumeStore, tmp_path: Path
) -> None:
    """Simulate the CLI dropping a PDF in by hand (no meta file)."""
    resume_dir = tmp_path / "resumes"
    resume_dir.mkdir(parents=True)
    (resume_dir / "alice.pdf").write_bytes(_FAKE_PDF)
    metadata = store.get_metadata("alice")
    assert metadata is not None
    assert metadata.filename == "alice.pdf"  # default fallback
    assert metadata.size_bytes == len(_FAKE_PDF)


def test_users_isolated(store: FileResumeStore) -> None:
    store.save_resume("alice", content=b"%PDF-1.4 a", filename="a.pdf")
    store.save_resume("bob", content=b"%PDF-1.4 bb", filename="b.pdf")
    assert store.get_file_bytes("alice") == b"%PDF-1.4 a"
    assert store.get_file_bytes("bob") == b"%PDF-1.4 bb"


def test_get_file_path_returns_path_when_exists(store: FileResumeStore) -> None:
    store.save_resume("alice", content=_FAKE_PDF, filename="r.pdf")
    path = store.get_file_path("alice")
    assert path is not None
    assert path.exists()


def test_get_file_path_returns_none_when_missing(store: FileResumeStore) -> None:
    assert store.get_file_path("alice") is None
