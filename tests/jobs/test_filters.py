"""Unit tests for the job exclusion filter."""

from role_tracker.jobs.filters import apply_exclusions, apply_title_relevance
from role_tracker.jobs.models import JobPosting


def _job(title: str, company: str, publisher: str = "unknown") -> JobPosting:
    return JobPosting(
        id="x",
        title=title,
        company=company,
        location="Toronto",
        description="",
        url="https://example.com",
        posted_at="2026-04-14T08:00:00Z",
        source="test",
        publisher=publisher,
    )


def test_exclude_by_company_substring_case_insensitive() -> None:
    jobs = [
        _job("Data Scientist", "TD Bank"),
        _job("Data Scientist", "Shopify"),
    ]
    kept, dropped = apply_exclusions(
        jobs, exclude_companies=["bank"], exclude_title_keywords=[]
    )
    assert [j.company for j in kept] == ["Shopify"]
    assert len(dropped) == 1
    assert "bank" in dropped[0].reason


def test_exclude_by_title_keyword() -> None:
    jobs = [
        _job("Banking Analyst", "Acme"),
        _job("Data Scientist", "Acme"),
    ]
    kept, dropped = apply_exclusions(
        jobs, exclude_companies=[], exclude_title_keywords=["banking"]
    )
    assert [j.title for j in kept] == ["Data Scientist"]
    assert len(dropped) == 1


def test_company_filter_runs_before_title_filter() -> None:
    jobs = [_job("Data Scientist", "Manulife")]
    kept, dropped = apply_exclusions(
        jobs, exclude_companies=["manulife"], exclude_title_keywords=["banking"]
    )
    assert kept == []
    assert "company contains 'manulife'" in dropped[0].reason


def test_empty_exclusion_lists_keep_everything() -> None:
    jobs = [_job("A", "X"), _job("B", "Y")]
    kept, dropped = apply_exclusions(
        jobs, exclude_companies=[], exclude_title_keywords=[]
    )
    assert len(kept) == 2
    assert dropped == []


def test_whitespace_and_case_are_normalized() -> None:
    jobs = [_job("Data Scientist", "  ROYAL BANK of Canada  ")]
    kept, dropped = apply_exclusions(
        jobs, exclude_companies=["royal bank"], exclude_title_keywords=[]
    )
    assert kept == []
    assert len(dropped) == 1


def test_exclude_by_publisher() -> None:
    jobs = [
        _job("Data Scientist", "Shopify", publisher="BeBee"),
        _job("Data Scientist", "Shopify", publisher="Shopify Careers"),
    ]
    kept, dropped = apply_exclusions(
        jobs,
        exclude_companies=[],
        exclude_title_keywords=[],
        exclude_publishers=["bebee"],
    )
    assert [j.publisher for j in kept] == ["Shopify Careers"]
    assert "publisher contains 'bebee'" in dropped[0].reason


def test_title_relevance_keeps_matching_jobs() -> None:
    jobs = [
        _job("Data Scientist", "Shopify"),
        _job("Senior Data Engineer", "Stripe"),
        _job("Backend Software Developer", "Snowflake"),
    ]
    kept, dropped = apply_title_relevance(jobs, ["data scientist"])
    titles = [j.title for j in kept]
    assert "Data Scientist" in titles
    assert "Senior Data Engineer" in titles  # matches "data"
    assert "Backend Software Developer" in [d.job.title for d in dropped]


def test_title_relevance_no_queries_keeps_all() -> None:
    jobs = [_job("Anything", "X"), _job("Other", "Y")]
    kept, dropped = apply_title_relevance(jobs, [])
    assert len(kept) == 2
    assert dropped == []


def test_title_relevance_strips_stopwords() -> None:
    jobs = [_job("Data Scientist", "X"), _job("Anything else", "Y")]
    # Query "in canada" → stopwords removed; "canada" is a real keyword.
    kept, dropped = apply_title_relevance(jobs, ["data scientist in canada"])
    # "Data Scientist" matches "data" or "scientist"; "Anything else" matches none.
    assert len(kept) == 1
    assert kept[0].title == "Data Scientist"
    assert dropped[0].job.title == "Anything else"
