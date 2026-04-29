"""JSearch API client (RapidAPI, wraps Google for Jobs) — implements JobSource.

Docs: https://rapidapi.com/letscrape-6bRBa3QguO5/api/jsearch
Returns full (non-truncated) job descriptions.
"""

import httpx

from role_tracker.jobs.models import JobPosting


class JSearchClient:
    """Thin wrapper around the JSearch API on RapidAPI."""

    name = "jsearch"
    BASE_URL = "https://jsearch.p.rapidapi.com/search"
    HOST = "jsearch.p.rapidapi.com"

    def __init__(
        self,
        rapidapi_key: str,
        country: str = "ca",
        date_posted: str = "week",
        exclude_publishers: list[str] | None = None,
        timeout: float = 120.0,
        http_client: httpx.Client | None = None,
    ) -> None:
        self._key = rapidapi_key
        self._country = country
        self._date_posted = date_posted  # "all", "today", "3days", "week", "month"
        self._exclude_publishers = exclude_publishers or []
        # 120s default — big page requests (num_pages=10+) can take 60–90s to
        # respond on the free tier.
        self._http = http_client or httpx.Client(timeout=timeout)

    def fetch_jobs(
        self, *, what: str, where: str, limit: int
    ) -> list[JobPosting]:
        """Fetch jobs. JSearch returns up to 10 per page — we page until `limit`."""
        results: list[JobPosting] = []
        pages_needed = max(1, (limit + 9) // 10)
        query = f"{what} in {where}" if where else what

        params: dict[str, str | int] = {
            "query": query,
            "page": 1,
            "num_pages": pages_needed,
            "country": self._country,
            "date_posted": self._date_posted,
        }
        if self._exclude_publishers:
            # JSearch takes a comma-separated list; it matches the publisher
            # name that would otherwise show up in job_publisher.
            params["exclude_job_publishers"] = ",".join(self._exclude_publishers)

        response = self._http.get(
            self.BASE_URL,
            headers={
                "x-rapidapi-key": self._key,
                "x-rapidapi-host": self.HOST,
            },
            params=params,
        )
        response.raise_for_status()
        data = response.json()
        for raw in data.get("data", [])[:limit]:
            results.append(self._parse(raw))
        return results

    @staticmethod
    def _parse(raw: dict) -> JobPosting:
        city = raw.get("job_city") or ""
        state = raw.get("job_state") or ""
        location = ", ".join(p for p in (city, state) if p) or "Unknown"
        return JobPosting(
            id=str(raw.get("job_id", "")),
            title=raw.get("job_title", "Unknown"),
            company=raw.get("employer_name", "Unknown"),
            location=location,
            description=raw.get("job_description", ""),
            url=raw.get("job_apply_link", ""),
            posted_at=raw.get("job_posted_at_datetime_utc", ""),
            salary_min=raw.get("job_min_salary"),
            salary_max=raw.get("job_max_salary"),
            source="jsearch",
            publisher=raw.get("job_publisher") or "unknown",
            employment_type=(raw.get("job_employment_type") or "").upper(),
        )
