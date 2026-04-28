"""Domain model for a stored cover letter (one version)."""

from datetime import datetime

from pydantic import BaseModel


class StoredLetter(BaseModel):
    """One version of a cover letter for one job.

    The agent's strategy and critique are persisted as opaque dicts because
    their shapes are owned by the cover_letter module and may evolve. The
    API layer projects them into typed Strategy / CritiqueScore models for
    the response.
    """

    job_id: str
    version: int                    # 1, 2, 3, ... (per job, monotonic)
    text: str                       # full letter Markdown
    word_count: int
    strategy: dict | None = None    # primary_project, narrative_angle, fit_*
    critique: dict | None = None    # rubric verdict + scores + fixes
    feedback_used: str | None = None  # populated for refined versions
    created_at: datetime
