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

    # 0 for the original generation, 1..MAX_REFINEMENTS_PER_LETTER for
    # successive refinements. Carries through manual edits unchanged.
    refinement_index: int = 0

    # True when this version was saved by the user via the manual-edit
    # endpoint (rather than the agent). Affects how the UI renders it
    # (no critique badge — agent's grade doesn't apply to user-edited text).
    edited_by_user: bool = False

    created_at: datetime
