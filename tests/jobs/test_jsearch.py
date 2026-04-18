"""Unit tests for the JSearch API client — no real HTTP calls."""

import json
from pathlib import Path
from unittest.mock import MagicMock

import httpx
import pytest

from role_tracker.jobs.jsearch import JSearchClient
from role_tracker.jobs.models import JobPosting

FIXTURE = Path(__file__).parent.parent / "fixtures" / "jsearch_response.json"


@pytest.fixture
def mock_http() -> MagicMock:
    raw = json.loads(FIXTURE.read_text())
    mock_response = MagicMock(spec=httpx.Response)
    mock_response.json.return_value = raw
    mock_response.raise_for_status.return_value = None
    mock_client = MagicMock(spec=httpx.Client)
    mock_client.get.return_value = mock_response
    return mock_client


def test_fetch_returns_job_postings(mock_http: MagicMock) -> None:
    client = JSearchClient(rapidapi_key="test_key", http_client=mock_http)
    jobs = client.fetch_jobs(what="ML engineer", where="canada", limit=20)
    assert len(jobs) == 2
    assert all(isinstance(j, JobPosting) for j in jobs)
    assert all(j.source == "jsearch" for j in jobs)


def test_fetch_parses_fields_correctly(mock_http: MagicMock) -> None:
    client = JSearchClient(rapidapi_key="test_key", http_client=mock_http)
    jobs = client.fetch_jobs(what="ML engineer", where="canada", limit=20)
    first = jobs[0]
    assert first.title == "Staff Machine Learning Engineer"
    assert first.company == "Shopify"
    assert first.location == "Toronto, Ontario"
    assert first.salary_min == 180000
    assert first.salary_max == 240000
    assert "ranking and recommendations" in first.description


def test_fetch_sends_rapidapi_headers(mock_http: MagicMock) -> None:
    client = JSearchClient(rapidapi_key="my_secret", http_client=mock_http)
    client.fetch_jobs(what="data scientist", where="canada", limit=20)
    headers = mock_http.get.call_args[1]["headers"]
    assert headers["x-rapidapi-key"] == "my_secret"
    assert headers["x-rapidapi-host"] == "jsearch.p.rapidapi.com"


def test_fetch_builds_query_string(mock_http: MagicMock) -> None:
    client = JSearchClient(rapidapi_key="k", http_client=mock_http)
    client.fetch_jobs(what="data scientist", where="halifax", limit=10)
    params = mock_http.get.call_args[1]["params"]
    assert params["query"] == "data scientist in halifax"
    assert params["country"] == "ca"


def test_fetch_respects_limit(mock_http: MagicMock) -> None:
    client = JSearchClient(rapidapi_key="k", http_client=mock_http)
    jobs = client.fetch_jobs(what="ML engineer", where="canada", limit=1)
    assert len(jobs) == 1


def test_fetch_parses_publisher(mock_http: MagicMock) -> None:
    client = JSearchClient(rapidapi_key="k", http_client=mock_http)
    jobs = client.fetch_jobs(what="ML engineer", where="canada", limit=20)
    assert jobs[0].publisher == "Shopify Careers"


def test_exclude_publishers_sends_csv_param(mock_http: MagicMock) -> None:
    client = JSearchClient(
        rapidapi_key="k",
        exclude_publishers=["BeBee", "Sercanto"],
        http_client=mock_http,
    )
    client.fetch_jobs(what="data scientist", where="canada", limit=10)
    params = mock_http.get.call_args[1]["params"]
    assert params["exclude_job_publishers"] == "BeBee,Sercanto"


def test_no_exclude_publishers_omits_param(mock_http: MagicMock) -> None:
    client = JSearchClient(rapidapi_key="k", http_client=mock_http)
    client.fetch_jobs(what="data scientist", where="canada", limit=10)
    params = mock_http.get.call_args[1]["params"]
    assert "exclude_job_publishers" not in params
