"""Haiku-based critique — Phase 4 Step 4.

Runs a separate Anthropic call (using the cheaper Haiku 4.5 model) to score a
cover-letter draft against the user's 100-point rubric. Returns a structured
result with verdict + priority fixes that the main agent uses to decide
whether to save or revise.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from anthropic import Anthropic

from role_tracker.jobs.models import JobPosting

CRITIQUE_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 2048

Context = Literal["COLD_APPLICATION", "WARM_INTRO"]

CRITIQUE_SYSTEM_PROMPT = """\
You are a strict cover-letter critic. Score the draft below against the rubric
and return a JSON object with the exact schema shown at the end. Do not return
any prose, commentary, or markdown fences — return ONLY valid JSON.

# Scoring Structure

Each category is scored 0–10 (or a different max per the table). Total = 100.

| Category | Weight | Max | Hard Threshold |
|---|---|---|---|
| 1. Hallucination / Grounding | 25% | 25 | Must score 25/25 |
| 2. Tailoring / JD References | 20% | 20 | Must score 14+ |
| 3. Voice & Human-Likeness | 15% | 15 | Must score 10+ |
| 4. Banned Phrases | 15% | 15 | Must score 12+ |
| 5. Structure & Length | 10% | 10 | — |
| 6. Gap Handling (context-aware) | 10% | 10 | — |
| 7. Opening & Closing Strength | 5% | 5 | — |

Verdict logic:
- Any hard threshold failed → verdict = "rewrite_required"
- Total >= 85 AND all thresholds met → verdict = "approved"
- Total 70–84 AND all thresholds met → verdict = "minor_revision"
- Total < 70 → verdict = "rewrite_required"

# Category 1: Hallucination / Grounding (25 points, hard threshold = 25)

Binary. 25 if every factual claim (technology, company, metric, project, degree,
year) traces to a specific resume section. 0 if any claim cannot be traced.

# Category 2: Tailoring / JD References (20 points, threshold = 14)

- 5 pts: Company name appears at least once AND correctly.
- 5 pts: Exact role title from the JD is used (not paraphrased).
- 5 pts: At least 2 specific JD details referenced (products, technologies,
  domains, responsibilities — not generic "your mission").
- 5 pts: Swap test — if company name were replaced with "[Company X]", the
  letter would not fit another company in the same field.

# Category 3: Voice & Human-Likeness (15 points, threshold = 10)

5 pts each:
- Sentence variance: short (<12 words) AND long (>20 words) sentences mixed.
- Contractions & natural transitions: >= 3 contractions; >= 1 sentence starts
  with "But", "And", or "So"; no stiff "Moreover" / "Furthermore".
- Specificity over abstraction.

# Category 4: Banned Phrases (15 points, threshold = 12)

Start at 15. Deduct:
- Em dash in prose: -2 per occurrence.
- Major LLM fingerprint (delve, pivotal, realm, showcase, cutting-edge,
  seamless, navigate as verb, leverage as verb, unleash/unlock metaphors,
  "at the intersection of", "passionate about"): -3 per occurrence.
- Cover-letter cliché (I am writing to express, I am excited/thrilled to
  apply, I would be a great fit, team player, self-starter, hit the ground
  running, perfect candidate): -2 per occurrence.
- Weak phrasing ("your company" instead of name, "I feel/believe" when facts
  would do, "various/numerous" without specifics): -1 per occurrence.
Floor is 0.

# Category 5: Structure & Length (10 points)

- 3 pts: Word count 300–400 (1 pt if 280–299 or 401–420, 0 if outside).
- 3 pts: 3 or 4 paragraphs (0 if 2 or fewer, or 5+).
- 2 pts: First paragraph hook is NOT "I am writing to...".
- 2 pts: Closing is "Best," or "Thanks," (not "Sincerely," / "Warmest regards").

# Category 6: Gap Handling (10 points, context-aware)

If context = WARM_INTRO:
- 10 pts: At most 1–2 gaps named, each paired with adjacent strength.
- 5 pts: Gaps named but pairing weak/delayed.
- 0 pts: 3+ gaps named, OR gap named without adjacent-strength pivot.

If context = COLD_APPLICATION:
- 10 pts: No gaps named. Letter focuses entirely on strengths.
- 5 pts: One gap hinted at but not explicitly named.
- 0 pts: Any explicit gap naming ("I haven't done X", "my experience in Y is
  limited", "I'll be upfront", "actively deepening").

# Category 7: Opening & Closing Strength (5 points)

- 2 pts: Opening sentence doesn't start with "I am..." AND mentions something
  specific to the role/company.
- 1 pt: Opening paragraph ends with a bridge to the candidate's strongest
  relevant point.
- 1 pt: Closing paragraph references something specific to the company.
- 1 pt: Sign-off is natural and brief.

# Output schema (return EXACTLY this structure)

{
  "scores": {
    "hallucination": {"score": 0-25, "threshold_met": bool, "unsupported": []},
    "tailoring": {"score": 0-20, "threshold_met": bool, "missing_references": [...]},
    "voice": {"score": 0-15, "threshold_met": bool, "concerns": [...]},
    "banned_phrases": {"score": 0-15, "threshold_met": bool, "violations": [...]},
    "structure": {"score": 0-10, "concerns": [...]},
    "gap_handling": {"score": 0-10, "concerns": [...]},
    "opening_closing": {"score": 0-5, "concerns": [...]}
  },
  "total": 0-100,
  "verdict": "approved" | "minor_revision" | "rewrite_required",
  "priority_fixes": ["specific fix 1", "specific fix 2", ...],
  "notes": "brief overall assessment"
}

Return ONLY the JSON. No markdown fences. No prose before or after.
"""


def _build_critique_user_message(
    *,
    draft: str,
    resume_text: str,
    job: JobPosting,
    context: Context,
) -> str:
    return (
        f"<context>{context}</context>\n\n"
        f"<job_description>\n"
        f"Title: {job.title}\n"
        f"Company: {job.company}\n\n"
        f"{job.description.strip()}\n"
        f"</job_description>\n\n"
        f"<resume>\n{resume_text.strip()}\n</resume>\n\n"
        f"<draft>\n{draft.strip()}\n</draft>\n\n"
        "Score the draft against the rubric. Return JSON only."
    )


def _extract_json(text: str) -> dict[str, Any] | None:
    """Pull a JSON object out of Haiku's response — tolerates stray text."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    # Fall back: find the first {...} block that parses.
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if match:
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None
    return None


def _fallback_result(raw_text: str) -> dict[str, Any]:
    """When Haiku's JSON can't be parsed, return a safe 'revise' verdict."""
    return {
        "scores": {},
        "total": 0,
        "verdict": "minor_revision",
        "priority_fixes": [
            "Critic output was not valid JSON — please review the draft manually "
            "and revise for grounding, tailoring, and banned phrases."
        ],
        "notes": f"Parse failure. Raw output: {raw_text[:200]}",
    }


def run_critique(
    *,
    draft: str,
    resume_text: str,
    job: JobPosting,
    client: Anthropic,
    context: Context = "COLD_APPLICATION",
    model: str = CRITIQUE_MODEL,
) -> dict[str, Any]:
    """Score a draft. Returns the rubric result (never raises on parse errors)."""
    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=CRITIQUE_SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": _build_critique_user_message(
                    draft=draft,
                    resume_text=resume_text,
                    job=job,
                    context=context,
                ),
            }
        ],
    )
    raw = "".join(b.text for b in response.content if b.type == "text")
    parsed = _extract_json(raw)
    if parsed is None:
        return _fallback_result(raw)
    return parsed


def format_for_agent(result: dict[str, Any]) -> str:
    """Render the rubric result as plain text the main agent can read back."""
    total = result.get("total", 0)
    verdict = result.get("verdict", "unknown")
    fixes = result.get("priority_fixes", [])
    notes = result.get("notes", "")

    # Surface which thresholds failed so the agent targets those first.
    failed = []
    for cat, s in (result.get("scores") or {}).items():
        if isinstance(s, dict) and s.get("threshold_met") is False:
            failed.append(f"{cat} ({s.get('score', '?')})")

    lines = [f"Total: {total}/100", f"Verdict: {verdict}"]
    if failed:
        lines.append("Failed thresholds: " + ", ".join(failed))
    if fixes:
        lines.append("Priority fixes:")
        for i, fix in enumerate(fixes, 1):
            lines.append(f"  {i}. {fix}")
    if notes:
        lines.append(f"Notes: {notes}")
    return "\n".join(lines)
