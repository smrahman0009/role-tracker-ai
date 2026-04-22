"""On-disk layout for cover-letter bundles.

One folder per letter, named so it sorts chronologically and is
self-explanatory on sight:

    data/cover_letters/<user_id>/<YYYY-MM-DD>_<company>_<title>_<hash>/
        cover_letter.md       — the generated letter
        job_description.md    — snapshot of the JD used as input
        resume_snapshot.txt   — the parsed resume text used as input
"""

import re
from datetime import date
from pathlib import Path

from role_tracker.jobs.models import JobPosting

DEFAULT_ROOT = Path("data/cover_letters")
_SLUG_CLEAN = re.compile(r"[^a-z0-9]+")
_SLUG_TRIM = re.compile(r"^-+|-+$")


def slugify(text: str, *, max_len: int = 40) -> str:
    """Normalize a string for use in a folder name — lowercase, hyphens, ASCII."""
    lowered = text.lower()
    hyphenated = _SLUG_CLEAN.sub("-", lowered)
    trimmed = _SLUG_TRIM.sub("", hyphenated)
    return trimmed[:max_len].rstrip("-") or "untitled"


def letter_folder_name(job: JobPosting, today: date | None = None) -> str:
    """Build the folder basename for one letter."""
    d = (today or date.today()).isoformat()
    company = slugify(job.company)
    title = slugify(job.title)
    # Last 6 chars of the job id disambiguate same-day duplicates from the
    # same employer. If the id is shorter, pad; if empty, fall back to "no-id".
    tail = (job.id or "no-id").replace("/", "_")[-6:] or "no-id"
    return f"{d}_{company}_{title}_{tail}"


def build_letter_dir(
    user_id: str,
    job: JobPosting,
    *,
    root: Path = DEFAULT_ROOT,
    today: date | None = None,
) -> Path:
    """Create and return the per-letter folder under data/cover_letters/<user>/."""
    folder = root / user_id / letter_folder_name(job, today=today)
    folder.mkdir(parents=True, exist_ok=True)
    return folder


def save_letter_bundle(
    *,
    folder: Path,
    letter_text: str,
    job: JobPosting,
    resume_text: str,
) -> None:
    """Write letter + JD snapshot + resume snapshot into the folder."""
    (folder / "cover_letter.md").write_text(letter_text.strip() + "\n")
    (folder / "job_description.md").write_text(_format_jd(job))
    (folder / "resume_snapshot.txt").write_text(resume_text.strip() + "\n")


def _format_jd(job: JobPosting) -> str:
    """Markdown snapshot of the JD — keeps all provenance next to the letter."""
    salary = ""
    if job.salary_min and job.salary_max:
        salary = f"- **Salary:** ${job.salary_min:,.0f} – ${job.salary_max:,.0f}\n"
    return (
        f"# {job.title}\n\n"
        f"- **Company:** {job.company}\n"
        f"- **Location:** {job.location}\n"
        f"- **Posted:** {job.posted_at[:10] if job.posted_at else 'unknown'}\n"
        f"- **Publisher:** {job.publisher}\n"
        f"- **Source:** {job.source}\n"
        f"{salary}"
        f"- **URL:** {job.url}\n\n"
        f"## Description\n\n"
        f"{job.description.strip()}\n"
    )
