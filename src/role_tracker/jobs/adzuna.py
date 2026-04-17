"""Adzuna API client and JobPosting data model."""

import httpx
from pydantic import BaseModel


class JobPosting(BaseModel):
    """A single job posting returned by the Adzuna API."""

    id: str
    title: str
    company: str
    location: str
    description: str
    url: str
    posted_at: str
    salary_min: float | None = None
    salary_max: float | None = None


class AdzunaClient:
    """Thin wrapper around the Adzuna jobs search API.

    Pass an httpx.Client explicitly in tests to avoid real HTTP calls.
    """

    BASE_URL = "https://api.adzuna.com/v1/api/jobs"

    def __init__(
        self,
        app_id: str,
        app_key: str,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._app_id = app_id
        self._app_key = app_key
        self._http = http_client or httpx.Client(timeout=30)

    def fetch_jobs(
        self,
        what: str,
        country: str = "ca",
        where: str = "canada",
        page: int = 1,
        results_per_page: int = 20,
    ) -> list[JobPosting]:
        """Fetch a page of jobs matching `what` in `where`."""
        url = f"{self.BASE_URL}/{country}/search/{page}"
        response = self._http.get(
            url,
            params={
                "app_id": self._app_id,
                "app_key": self._app_key,
                "results_per_page": results_per_page,
                "what": what,
                "where": where,
                "content-type": "application/json",
            },
        )
        response.raise_for_status()
        data = response.json()
        return [self._parse(r) for r in data.get("results", [])]

    @staticmethod
    def _parse(raw: dict) -> JobPosting:
        return JobPosting(
            id=str(raw["id"]),
            title=raw["title"],
            company=raw.get("company", {}).get("display_name", "Unknown"),
            location=raw.get("location", {}).get("display_name", "Unknown"),
            description=raw.get("description", ""),
            url=raw.get("redirect_url", ""),
            posted_at=raw.get("created", ""),
            salary_min=raw.get("salary_min"),
            salary_max=raw.get("salary_max"),
        )
