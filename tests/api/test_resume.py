"""Tests for resume upload / metadata / download endpoints."""

from collections.abc import Iterator
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from role_tracker.api.main import create_app
from role_tracker.api.routes.profile import get_profile_store
from role_tracker.api.routes.resume import get_resume_store
from role_tracker.resume.store import FileResumeStore
from role_tracker.users.yaml_store import YamlUserProfileStore

_FAKE_PDF = b"%PDF-1.4\n% fake content\n%%EOF\n"


@pytest.fixture
def client(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Iterator[TestClient]:
    monkeypatch.delenv("APP_TOKEN", raising=False)
    app = create_app()
    test_store = FileResumeStore(root=tmp_path / "resumes")
    test_profiles = YamlUserProfileStore(root=tmp_path / "users")
    app.dependency_overrides[get_resume_store] = lambda: test_store
    app.dependency_overrides[get_profile_store] = lambda: test_profiles
    # Default: parse_resume returns empty so the autofill path is a no-op.
    # Individual tests monkeypatch this when they need real extracted text.
    import role_tracker.api.routes.resume as resume_module
    monkeypatch.setattr(resume_module, "parse_resume", lambda _: "")
    with TestClient(app) as c:
        yield c


def test_get_metadata_404_when_no_resume(client: TestClient) -> None:
    response = client.get("/users/alice/resume")
    assert response.status_code == 404


def test_download_404_when_no_resume(client: TestClient) -> None:
    response = client.get("/users/alice/resume/file")
    assert response.status_code == 404


def test_upload_returns_201_and_metadata(client: TestClient) -> None:
    response = client.post(
        "/users/alice/resume",
        files={"file": ("MyResume.pdf", _FAKE_PDF, "application/pdf")},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["filename"] == "MyResume.pdf"
    assert body["size_bytes"] == len(_FAKE_PDF)
    assert len(body["sha256"]) == 64


def test_upload_then_get_metadata(client: TestClient) -> None:
    client.post(
        "/users/alice/resume",
        files={"file": ("Resume.pdf", _FAKE_PDF, "application/pdf")},
    )
    response = client.get("/users/alice/resume")
    assert response.status_code == 200
    assert response.json()["filename"] == "Resume.pdf"


def test_upload_then_download(client: TestClient) -> None:
    client.post(
        "/users/alice/resume",
        files={"file": ("Resume.pdf", _FAKE_PDF, "application/pdf")},
    )
    response = client.get("/users/alice/resume/file")
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/pdf"
    assert response.content == _FAKE_PDF


def test_upload_replaces_previous(client: TestClient) -> None:
    client.post(
        "/users/alice/resume",
        files={"file": ("v1.pdf", b"%PDF-1.4 first", "application/pdf")},
    )
    client.post(
        "/users/alice/resume",
        files={"file": ("v2.pdf", b"%PDF-1.4 second", "application/pdf")},
    )
    metadata = client.get("/users/alice/resume").json()
    assert metadata["filename"] == "v2.pdf"
    assert client.get("/users/alice/resume/file").content == b"%PDF-1.4 second"


def test_upload_rejects_non_pdf_content(client: TestClient) -> None:
    """No %PDF- header → rejected even if filename ends in .pdf."""
    response = client.post(
        "/users/alice/resume",
        files={"file": ("fake.pdf", b"not a pdf", "application/pdf")},
    )
    assert response.status_code == 400
    assert "PDF" in response.json()["detail"]


def test_upload_rejects_oversized_file(client: TestClient) -> None:
    big_content = b"%PDF-1.4" + (b"a" * (5 * 1024 * 1024 + 1))
    response = client.post(
        "/users/alice/resume",
        files={"file": ("big.pdf", big_content, "application/pdf")},
    )
    assert response.status_code == 413


def test_users_isolated(client: TestClient) -> None:
    client.post(
        "/users/alice/resume",
        files={"file": ("a.pdf", b"%PDF-1.4 alice", "application/pdf")},
    )
    client.post(
        "/users/bob/resume",
        files={"file": ("b.pdf", b"%PDF-1.4 bob's", "application/pdf")},
    )
    assert client.get("/users/alice/resume").json()["filename"] == "a.pdf"
    assert client.get("/users/bob/resume").json()["filename"] == "b.pdf"


# ----- contact info auto-fill -----


_RESUME_TEXT = (
    "Jane Doe\n"
    "Halifax, NS · +1 (902) 555-1234 · jane@example.com\n"
    "linkedin.com/in/jane-doe · github.com/janedoe\n"
)


def test_upload_returns_prefilled_field_list(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    import role_tracker.api.routes.resume as resume_module

    monkeypatch.setattr(resume_module, "parse_resume", lambda _: _RESUME_TEXT)

    response = client.post(
        "/users/alice/resume",
        files={"file": ("r.pdf", _FAKE_PDF, "application/pdf")},
    )
    assert response.status_code == 201
    body = response.json()
    prefilled = set(body["prefilled_fields"])
    assert {"name", "email", "phone", "linkedin_url", "github_url"} <= prefilled


def test_upload_persists_extracted_fields_to_profile(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    import role_tracker.api.routes.resume as resume_module

    monkeypatch.setattr(resume_module, "parse_resume", lambda _: _RESUME_TEXT)

    client.post(
        "/users/alice/resume",
        files={"file": ("r.pdf", _FAKE_PDF, "application/pdf")},
    )
    profile = client.get("/users/alice/profile").json()
    assert profile["name"] == "Jane Doe"
    assert profile["email"] == "jane@example.com"
    assert "902" in profile["phone"]
    assert "jane-doe" in profile["linkedin_url"]
    assert "janedoe" in profile["github_url"]


def test_upload_does_not_overwrite_existing_profile_fields(
    monkeypatch: pytest.MonkeyPatch, client: TestClient
) -> None:
    """User-typed values win over anything we extract from the PDF."""
    import role_tracker.api.routes.resume as resume_module

    monkeypatch.setattr(resume_module, "parse_resume", lambda _: _RESUME_TEXT)

    # User typed their preferred email first.
    client.put(
        "/users/alice/profile",
        json={"name": "Alice Custom", "email": "alice@custom.com"},
    )
    response = client.post(
        "/users/alice/resume",
        files={"file": ("r.pdf", _FAKE_PDF, "application/pdf")},
    )
    # Phone, linkedin, github were blank → filled.
    prefilled = set(response.json()["prefilled_fields"])
    assert "phone" in prefilled
    assert "linkedin_url" in prefilled
    # Name and email were already set → not overwritten, not in prefilled.
    assert "name" not in prefilled
    assert "email" not in prefilled

    profile = client.get("/users/alice/profile").json()
    assert profile["name"] == "Alice Custom"
    assert profile["email"] == "alice@custom.com"
    assert "902" in profile["phone"]


def test_upload_returns_empty_prefilled_when_pdf_has_no_contact_info(
    client: TestClient,
) -> None:
    """Default fixture parses to empty string — no fields can be extracted."""
    response = client.post(
        "/users/alice/resume",
        files={"file": ("r.pdf", _FAKE_PDF, "application/pdf")},
    )
    assert response.json()["prefilled_fields"] == []
