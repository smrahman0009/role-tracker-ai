"""Tools for the cover-letter agent — Phase 4 Step 3.

Tools are capabilities the agent (Claude) can invoke during its loop. Each has:
  - A JSON schema Claude reads to decide when/how to call it.
  - A Python implementation that runs when Claude requests it.

The agent CANNOT see the full resume or JD until it fetches them. This forces
deliberate choices about what to look at — which is the whole point of moving
from "stuff everything in the prompt" (Step 1) to "agent fetches what it needs".
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from anthropic import Anthropic

from role_tracker.cover_letter.critique import (
    Context,
    format_for_agent,
    run_critique,
)
from role_tracker.jobs.models import JobPosting

MAX_CRITIQUES = 3  # initial + up to 2 revisions

# JSON schemas for Claude. The description field matters most — Claude reads
# these to decide which tool to call and when.
TOOL_SCHEMAS: list[dict[str, Any]] = [
    {
        "name": "read_job_description",
        "description": (
            "Return the full job description for the role the candidate is "
            "applying to. Call this FIRST to understand what the job actually "
            "requires before looking up resume content."
        ),
        "input_schema": {
            "type": "object",
            "properties": {},
            "required": [],
        },
    },
    {
        "name": "read_resume_section",
        "description": (
            "Search the candidate's resume for content matching a topic. "
            "Returns the paragraphs that contain the topic (case-insensitive). "
            "Use specific topics like 'transformers', 'Azure', 'Everstream', "
            "'commodity classification', 'education'. If nothing matches, try "
            "a broader or different term. Do NOT try to recall resume content "
            "from memory — always use this tool to verify."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "topic": {
                    "type": "string",
                    "description": (
                        "Keyword or short phrase to search for in the resume."
                    ),
                }
            },
            "required": ["topic"],
        },
    },
    {
        "name": "critique_draft",
        "description": (
            "Score a draft cover letter against a 100-point rubric (Hallucination, "
            "Tailoring, Voice, Banned Phrases, Structure, Gap Handling, "
            "Opening/Closing). Returns the total score, verdict "
            "('approved', 'minor_revision', 'rewrite_required'), failed "
            "thresholds, and priority fixes. Call this BEFORE save_letter. "
            "If the verdict is not 'approved', revise using the priority "
            "fixes and call critique_draft again. Max 3 critiques per letter."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "draft": {
                    "type": "string",
                    "description": (
                        "The full draft letter text to be scored, including "
                        "header, greeting, body, and sign-off."
                    ),
                }
            },
            "required": ["draft"],
        },
    },
    {
        "name": "save_letter",
        "description": (
            "Save the final cover letter and end the task. Call this ONLY "
            "after critique_draft returns 'approved', OR after you have "
            "used all available critique attempts. After calling this, "
            "do not produce any further output."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {
                    "type": "string",
                    "description": (
                        "The complete final cover letter text, including the "
                        "header block, greeting, body, sign-off, and name."
                    ),
                }
            },
            "required": ["text"],
        },
    },
]


def _split_resume_chunks(resume_text: str) -> list[str]:
    """Break resume into paragraph-sized chunks for keyword lookup."""
    return [p.strip() for p in resume_text.split("\n\n") if p.strip()]


def build_tool_executors(
    *,
    resume_text: str,
    job: JobPosting,
    anthropic_client: Anthropic | None = None,
    context: Context = "COLD_APPLICATION",
) -> tuple[dict[str, Callable[..., str]], dict[str, Any]]:
    """Build Python functions that actually execute each tool.

    Returns (executors, state). State holds anything the agent persists
    across iterations: saved letter, tool-call count, critique history.

    The Anthropic client is used by the critique tool to call Haiku.
    If not provided, critique_draft returns a fallback 'approved' verdict
    (used in unit tests that don't exercise the critique path).
    """
    chunks = _split_resume_chunks(resume_text)
    state: dict[str, Any] = {
        "saved_letter": None,
        "tool_call_count": 0,
        "critique_count": 0,
        "last_critique": None,
    }

    def read_job_description() -> str:
        state["tool_call_count"] += 1
        salary = ""
        if job.salary_min and job.salary_max:
            salary = f"Salary: ${job.salary_min:,.0f} – ${job.salary_max:,.0f}\n"
        return (
            f"Title: {job.title}\n"
            f"Company: {job.company}\n"
            f"Location: {job.location}\n"
            f"{salary}"
            f"\nDescription:\n{job.description.strip()}"
        )

    def read_resume_section(topic: str) -> str:
        state["tool_call_count"] += 1
        needle = topic.lower().strip()
        matches = [c for c in chunks if needle in c.lower()]
        if not matches:
            return (
                f"No resume content found for '{topic}'. "
                "Try a broader or different term."
            )
        return "\n\n---\n\n".join(matches)

    def critique_draft(draft: str) -> str:
        state["tool_call_count"] += 1
        state["critique_count"] += 1
        if state["critique_count"] > MAX_CRITIQUES:
            return (
                f"Max critiques reached ({MAX_CRITIQUES}). "
                "Call save_letter with your current best draft."
            )
        if anthropic_client is None:
            # Unit-test path — no client was wired up, auto-approve.
            result = {
                "total": 100,
                "verdict": "approved",
                "priority_fixes": [],
                "scores": {},
                "notes": "No critique client configured (test mode).",
            }
        else:
            result = run_critique(
                draft=draft,
                resume_text=resume_text,
                job=job,
                client=anthropic_client,
                context=context,
            )
        state["last_critique"] = result
        budget_note = (
            f"\n(Critiques used: {state['critique_count']}/{MAX_CRITIQUES})"
        )
        return format_for_agent(result) + budget_note

    def save_letter(text: str) -> str:
        state["tool_call_count"] += 1
        state["saved_letter"] = text
        word_count = len(text.split())
        return f"Letter saved ({word_count} words). Task complete."

    return (
        {
            "read_job_description": read_job_description,
            "read_resume_section": read_resume_section,
            "critique_draft": critique_draft,
            "save_letter": save_letter,
        },
        state,
    )
