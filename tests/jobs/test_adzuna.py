"""Unit tests for the Adzuna API client — no real HTTP calls."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from role_tracker.jobs.adzuna import AdzunaClient, JobPosting

FIXTURE = Path(__file__).parent.parent / "fixtures" / "adzuna_response.json"


@pytest.fixture
def mock_http() -> MagicMock:
    """httpx.Client that returns the recorded fixture instead of hitting the API."""
    raw = json.loads(FIXTURE.read_text())
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = raw
    mock_response.raise_for_status.return_value = None
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.return_value = mock_response
    return mock_client


def test_fetch_returns_job_postings(mock_http: MagicMock) -> None:
    client = AdzunaClient(app_id="test_id", app_key="test_key", http_client=mock_http)
    jobs = client.fetch_jobs(what="data scientist")
    assert len(jobs) == 2
    assert all(isinstance(j, JobPosting) for j in jobs)


def test_fetch_parses_fields_correctly(mock_http: MagicMock) -> None:
    client = AdzunaClient(app_id="test_id", app_key="test_key", http_client=mock_http)
    jobs = client.fetch_jobs(what="data scientist")
    first = jobs[0]
    assert first.title == "Senior Data Scientist"
    assert first.company == "Shopify"
    assert first.location == "Toronto, Ontario"
    assert first.salary_min == 120000
    assert first.salary_max == 160000
    assert first.id == "4839201847"


def test_fetch_calls_correct_url(mock_http: MagicMock) -> None:
    client = AdzunaClient(app_id="test_id", app_key="test_key", http_client=mock_http)
    client.fetch_jobs(what="data scientist", country="ca", page=1)
    mock_http.get.assert_called_once()
    url_called = mock_http.get.call_args[0][0]
    assert "ca/search/1" in url_called


def test_fetch_passes_credentials(mock_http: MagicMock) -> None:
    client = AdzunaClient(app_id="my_id", app_key="my_key", http_client=mock_http)
    client.fetch_jobs(what="data scientist")
    params = mock_http.get.call_args[1]["params"]
    assert params["app_id"] == "my_id"
    assert params["app_key"] == "my_key"
