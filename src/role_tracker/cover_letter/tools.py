"""Tools for the cover-letter agent — Phase 4 architectural rebuild.

Tools are capabilities the agent (Claude) can invoke during its loop. Each has:
  - A JSON schema Claude reads to decide when/how to call it.
  - A Python implementation that runs when Claude requests it.

The agent CANNOT see the full resume or JD until it fetches them. This forces
deliberate choices about what to look at — which is the whole point of moving
from "stuff everything in the prompt" to "agent fetches what it needs".

The architectural rebuild adds:
  - commit_to_strategy: forced planning step before drafting (one narrative
    angle, one primary project, optional secondary, fit assessment).
  - Hard deterministic post-save checks for word count + paragraph length.
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
MAX_SAVE_RETRIES = 2  # if deterministic post-save checks fail
MIN_WORDS = 280
MAX_WORDS = 420
MAX_PARAGRAPH_WORDS = 130

FitAssessment = ["HIGH", "MEDIUM", "LOW"]

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
        "name": "commit_to_strategy",
        "description": (
            "Commit to a single narrative strategy BEFORE drafting. This is a "
            "mandatory planning step — you cannot save a letter without "
            "calling this first. You assess role-fit, pick ONE primary "
            "project as the spine of the letter, and at most ONE secondary "
            "project. Everything else stays out. The committed strategy is "
            "passed to the critic, which checks the letter actually executes "
            "your plan. You can only commit ONCE per letter."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "fit_assessment": {
                    "type": "string",
                    "enum": ["HIGH", "MEDIUM", "LOW"],
                    "description": (
                        "How well the resume matches the role. HIGH = "
                        "candidate has direct experience for most "
                        "requirements. MEDIUM = candidate has adjacent or "
                        "transferable experience that can be honestly "
                        "bridged. LOW = candidate is missing major "
                        "requirements with no honest bridge available."
                    ),
                },
                "fit_reasoning": {
                    "type": "string",
                    "description": (
                        "One or two sentences justifying the fit assessment. "
                        "Reference specific JD requirements + resume content."
                    ),
                },
                "narrative_angle": {
                    "type": "string",
                    "description": (
                        "One sentence describing the SINGLE through-line of "
                        "the letter. Example: 'My production NLP work on "
                        "entity resolution maps directly to the matching "
                        "and ranking core of recommendation systems.'"
                    ),
                },
                "primary_project": {
                    "type": "string",
                    "description": (
                        "The ONE project that will be the spine of the "
                        "letter, mentioned in para 1, elaborated in para 2, "
                        "and referenced in para 3."
                    ),
                },
                "secondary_project": {
                    "type": "string",
                    "description": (
                        "Optional. At most ONE additional project that "
                        "supports the primary. Leave empty if none needed. "
                        "Do NOT add a third project."
                    ),
                },
            },
            "required": [
                "fit_assessment",
                "fit_reasoning",
                "narrative_angle",
                "primary_project",
            ],
        },
    },
    {
        "name": "critique_draft",
        "description": (
            "Score a draft cover letter against a 110-point rubric. Returns "
            "the total score, verdict ('approved', 'minor_revision', "
            "'rewrite_required'), failed thresholds, and priority fixes. "
            "Call this AFTER commit_to_strategy and BEFORE save_letter. "
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
            "Save the final cover letter and end the task. PRECONDITIONS: "
            "you must have called commit_to_strategy AND at least one "
            "critique_draft. The letter must be 280-420 words with no "
            "paragraph longer than 130 words — if it fails these "
            "deterministic checks, save_letter will reject it and ask "
            "you to revise. You get 2 save retries."
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


def _validate_letter(text: str) -> list[str]:
    """Run deterministic checks on a saved letter. Returns list of failures."""
    failures: list[str] = []
    word_count = len(text.split())
    if word_count < MIN_WORDS:
        failures.append(
            f"Letter is {word_count} words. Minimum is {MIN_WORDS}. "
            "Expand with more concrete detail (NOT new claims)."
        )
    if word_count > MAX_WORDS:
        failures.append(
            f"Letter is {word_count} words. Maximum is {MAX_WORDS}. "
            "Cut secondary material; keep the primary project as spine."
        )
    paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
    for i, para in enumerate(paragraphs, 1):
        para_words = len(para.split())
        if para_words > MAX_PARAGRAPH_WORDS:
            failures.append(
                f"Paragraph {i} is {para_words} words. "
                f"Maximum is {MAX_PARAGRAPH_WORDS}. Split or cut."
            )
    return failures


def build_tool_executors(
    *,
    resume_text: str,
    job: JobPosting,
    anthropic_client: Anthropic | None = None,
    context: Context = "COLD_APPLICATION",
) -> tuple[dict[str, Callable[..., str]], dict[str, Any]]:
    """Build Python functions that actually execute each tool.

    Returns (executors, state). State holds anything the agent persists
    across iterations: saved letter, tool-call count, critique history,
    committed strategy.
    """
    chunks = _split_resume_chunks(resume_text)
    state: dict[str, Any] = {
        "saved_letter": None,
        "tool_call_count": 0,
        "critique_count": 0,
        "last_critique": None,
        "strategy": None,
        "save_retries": 0,
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

    def commit_to_strategy(
        fit_assessment: str,
        fit_reasoning: str,
        narrative_angle: str,
        primary_project: str,
        secondary_project: str = "",
    ) -> str:
        state["tool_call_count"] += 1
        if state["strategy"] is not None:
            return (
                "Strategy already committed. You cannot change it mid-letter. "
                "Stick with the original plan or revise the draft within it."
            )
        state["strategy"] = {
            "fit_assessment": fit_assessment,
            "fit_reasoning": fit_reasoning,
            "narrative_angle": narrative_angle,
            "primary_project": primary_project,
            "secondary_project": secondary_project,
        }
        return (
            f"Strategy committed.\n"
            f"  Fit: {fit_assessment}\n"
            f"  Angle: {narrative_angle}\n"
            f"  Primary: {primary_project}\n"
            f"  Secondary: {secondary_project or '(none)'}\n\n"
            "Now draft the letter. The primary project should be the spine: "
            "introduced in para 1, elaborated in para 2, referenced in para 3. "
            "Do not introduce projects outside this strategy."
        )

    def critique_draft(draft: str) -> str:
        state["tool_call_count"] += 1
        if state["strategy"] is None:
            return (
                "Cannot critique before strategy is committed. "
                "Call commit_to_strategy first."
            )
        state["critique_count"] += 1
        if state["critique_count"] > MAX_CRITIQUES:
            return (
                f"Max critiques reached ({MAX_CRITIQUES}). "
                "Call save_letter with your current best draft."
            )
        if anthropic_client is None:
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
                strategy=state["strategy"],
            )
        state["last_critique"] = result
        budget_note = (
            f"\n(Critiques used: {state['critique_count']}/{MAX_CRITIQUES})"
        )
        return format_for_agent(result) + budget_note

    def save_letter(text: str) -> str:
        state["tool_call_count"] += 1
        if state["strategy"] is None:
            return (
                "Refused: no strategy committed. "
                "Call commit_to_strategy before drafting."
            )
        if state["critique_count"] == 0:
            return (
                "Refused: no critique run yet. Call critique_draft "
                "at least once before saving."
            )
        failures = _validate_letter(text)
        if failures:
            state["save_retries"] += 1
            if state["save_retries"] > MAX_SAVE_RETRIES:
                # Out of retries — accept it and let the user see the issues.
                state["saved_letter"] = text
                return (
                    f"Saved (with {len(failures)} unresolved issues). "
                    "User will review."
                )
            joined = "\n  - ".join(failures)
            return (
                f"Refused — letter failed deterministic checks:\n  - {joined}\n\n"
                f"Revise and call save_letter again "
                f"(retry {state['save_retries']}/{MAX_SAVE_RETRIES})."
            )
        state["saved_letter"] = text
        word_count = len(text.split())
        return f"Letter saved ({word_count} words). Task complete."

    return (
        {
            "read_job_description": read_job_description,
            "read_resume_section": read_resume_section,
            "commit_to_strategy": commit_to_strategy,
            "critique_draft": critique_draft,
            "save_letter": save_letter,
        },
        state,
    )
