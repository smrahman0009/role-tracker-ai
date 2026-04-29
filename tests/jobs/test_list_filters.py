"""Tests for apply_list_filters — the inline filter-chip logic."""

from datetime import UTC, datetime, timedelta

from role_tracker.jobs.filters import apply_list_filters
from role_tracker.jobs.models import JobPosting


def _job(
    *,
    title: str = "Data Scientist",
    location: str = "Toronto",
    salary_min: float | None = None,
    employment_type: str = "FULLTIME",
    posted_at: str | None = None,
) -> JobPosting:
    return JobPosting(
        id=title + location,
        title=title,
        company="Acme",
        location=location,
        description="x",
        url="https://example.com",
        posted_at=posted_at or datetime.now(UTC).isoformat(),
        salary_min=salary_min,
        source="jsearch",
        publisher="Acme Careers",
        employment_type=employment_type,
    )


# ----- type -----


def test_type_filter_or_logic_within_values() -> None:
    jobs = [
        _job(title="Senior Data Scientist"),
        _job(title="Machine Learning Engineer"),
        _job(title="Backend Developer"),
    ]
    out = apply_list_filters(
        jobs,
        type_terms=["data scientist", "ml engineer"],
        location_terms=[],
        salary_min=None,
        hide_no_salary=False,
        employment_types=[],
        posted_within_days=None,
    )
    assert len(out) == 1  # Only "Senior Data Scientist" matches
    assert out[0].title == "Senior Data Scientist"


def test_type_filter_case_insensitive() -> None:
    jobs = [_job(title="Lead Data Scientist")]
    assert (
        len(
            apply_list_filters(
                jobs,
                type_terms=["DATA SCIENTIST"],
                location_terms=[],
                salary_min=None,
                hide_no_salary=False,
                employment_types=[],
                posted_within_days=None,
            )
        )
        == 1
    )


def test_empty_type_filter_keeps_all() -> None:
    jobs = [_job(title="Anything")]
    assert (
        len(
            apply_list_filters(
                jobs,
                type_terms=[],
                location_terms=[],
                salary_min=None,
                hide_no_salary=False,
                employment_types=[],
                posted_within_days=None,
            )
        )
        == 1
    )


# ----- location -----


def test_location_filter_or_logic() -> None:
    jobs = [
        _job(location="Toronto, ON"),
        _job(location="Vancouver, BC"),
        _job(location="Halifax, NS"),
    ]
    out = apply_list_filters(
        jobs,
        type_terms=[],
        location_terms=["toronto", "vancouver"],
        salary_min=None,
        hide_no_salary=False,
        employment_types=[],
        posted_within_days=None,
    )
    assert {j.location for j in out} == {"Toronto, ON", "Vancouver, BC"}


# ----- salary -----


def test_salary_min_keeps_no_salary_by_default() -> None:
    jobs = [
        _job(title="A", salary_min=90000),
        _job(title="B", salary_min=70000),
        _job(title="C", salary_min=None),
    ]
    out = apply_list_filters(
        jobs,
        type_terms=[],
        location_terms=[],
        salary_min=80000,
        hide_no_salary=False,
        employment_types=[],
        posted_within_days=None,
    )
    titles = {j.title for j in out}
    assert "A" in titles      # 90k passes
    assert "B" not in titles  # 70k drops
    assert "C" in titles      # no salary -> kept (lenient)


def test_hide_no_salary_drops_jobs_without_listed_salary() -> None:
    jobs = [_job(title="X", salary_min=None)]
    assert (
        apply_list_filters(
            jobs,
            type_terms=[],
            location_terms=[],
            salary_min=80000,
            hide_no_salary=True,
            employment_types=[],
            posted_within_days=None,
        )
        == []
    )


# ----- employment type -----


def test_employment_type_filter() -> None:
    jobs = [
        _job(title="A", employment_type="FULLTIME"),
        _job(title="B", employment_type="CONTRACTOR"),
        _job(title="C", employment_type="INTERN"),
    ]
    out = apply_list_filters(
        jobs,
        type_terms=[],
        location_terms=[],
        salary_min=None,
        hide_no_salary=False,
        employment_types=["FULLTIME", "CONTRACTOR"],
        posted_within_days=None,
    )
    assert {j.title for j in out} == {"A", "B"}


def test_empty_employment_type_passes_through() -> None:
    """Jobs with no employment_type tagged shouldn't be dropped by the filter."""
    jobs = [_job(title="X", employment_type="")]
    out = apply_list_filters(
        jobs,
        type_terms=[],
        location_terms=[],
        salary_min=None,
        hide_no_salary=False,
        employment_types=["FULLTIME"],
        posted_within_days=None,
    )
    assert len(out) == 1


# ----- posted within -----


def test_posted_within_drops_old_jobs() -> None:
    now = datetime.now(UTC)
    jobs = [
        _job(title="recent", posted_at=(now - timedelta(days=2)).isoformat()),
        _job(title="old", posted_at=(now - timedelta(days=40)).isoformat()),
    ]
    out = apply_list_filters(
        jobs,
        type_terms=[],
        location_terms=[],
        salary_min=None,
        hide_no_salary=False,
        employment_types=[],
        posted_within_days=7,
    )
    assert {j.title for j in out} == {"recent"}


def test_unparseable_posted_at_is_kept() -> None:
    jobs = [_job(title="x", posted_at="not-a-date")]
    out = apply_list_filters(
        jobs,
        type_terms=[],
        location_terms=[],
        salary_min=None,
        hide_no_salary=False,
        employment_types=[],
        posted_within_days=7,
    )
    assert len(out) == 1


# ----- combined -----


def test_filters_combined_and_logic_across_dimensions() -> None:
    """Job must pass ALL filter dimensions (AND across filter types)."""
    jobs = [
        _job(title="Data Scientist", location="Toronto", salary_min=100000),
        # wrong location:
        _job(title="Data Scientist", location="Halifax", salary_min=100000),
        # below salary minimum:
        _job(title="Data Scientist", location="Toronto", salary_min=50000),
        # wrong job type:
        _job(title="Backend Engineer", location="Toronto", salary_min=100000),
    ]
    out = apply_list_filters(
        jobs,
        type_terms=["data scientist"],
        location_terms=["toronto"],
        salary_min=80000,
        hide_no_salary=False,
        employment_types=[],
        posted_within_days=None,
    )
    assert len(out) == 1
