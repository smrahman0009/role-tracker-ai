"""Haiku-based critique — Phase 4 architectural rebuild.

Runs a separate Anthropic call (using the cheaper Haiku 4.5 model) to score a
cover-letter draft against the user's rubric. The rubric was tightened in
the rebuild to:
  - treat hedge words ("familiar with", "informally applied", etc.) as
    ungrounded factual claims that fail Category 1
  - add a Narrative Coherence category (10 pts, hard threshold 7+)
  - check whether the letter actually executed the agent's committed strategy

Total scale grew from 100 to 110.
"""

from __future__ import annotations

import json
import re
from typing import Any, Literal

from anthropic import Anthropic

from role_tracker.jobs.models import JobPosting

CRITIQUE_MODEL = "claude-haiku-4-5-20251001"
MAX_TOKENS = 4096

Context = Literal["COLD_APPLICATION", "WARM_INTRO"]

CRITIQUE_SYSTEM_PROMPT = """\
You are a strict cover-letter critic. Score the draft below against the rubric
and return a JSON object with the exact schema shown at the end. Do not return
any prose, commentary, or markdown fences — return ONLY valid JSON.

Be tough. Letters that pass without revision should genuinely deserve it. When
in doubt, fail the threshold.

# Scoring Structure

Total = 110 points across 8 categories.

| Category | Max | Hard Threshold |
|---|---|---|
| 1. Hallucination / Grounding | 25 | Must score 25/25 |
| 2. Tailoring / JD References | 20 | Must score 14+ |
| 3. Voice & Human-Likeness | 15 | Must score 10+ |
| 4. Banned Phrases | 15 | Must score 12+ |
| 5. Structure & Length | 10 | — |
| 6. Gap Handling (context-aware) | 10 | — |
| 7. Opening & Closing Strength | 5 | — |
| 8. Narrative Coherence | 10 | Must score 7+ |

Verdict logic:
- Any hard threshold failed → verdict = "rewrite_required"
- Total >= 94 (85% of 110) AND all thresholds met → verdict = "approved"
- Total 77-93 AND all thresholds met → verdict = "minor_revision"
- Total < 77 → verdict = "rewrite_required"

# Category 1: Hallucination / Grounding (25 points, hard threshold = 25)

ZERO TOLERANCE. 25 if every factual claim in the letter — including HEDGED
claims — traces to a specific resume section. 0 if any single claim cannot
be traced.

CRITICAL: hedge words DO NOT exempt a claim from grounding. The following
phrasings ARE factual claims that must be backed by the resume:
- "I'm familiar with X"
- "I have exposure to X"
- "I've informally applied X"
- "I've worked with X concepts"
- "I'm comfortable with X"
- "I've been close to X workflows"
- "I've started ramping up on X"
- "I'm actively deepening X"
- "I have working knowledge of X"

If X is not in the resume, ALL of these score 0. There is no soft middle ground.

When you find a violation, list it in `unsupported`. Be precise: name the
exact phrase and the resume section that should have backed it.

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

- 3 pts: Word count 300-400 (1 pt if 280-299 or 401-420, 0 if outside).
- 3 pts: 3 or 4 paragraphs (0 if 2 or fewer, or 5+).
- 2 pts: First paragraph hook is NOT "I am writing to...".
- 2 pts: Closing is "Best," or "Thanks," (not "Sincerely,").

# Category 6: Gap Handling (10 points, context-aware)

If context = WARM_INTRO:
- 10 pts: At most 1-2 gaps named, each paired with adjacent strength.
- 5 pts: Gaps named but pairing weak or delayed.
- 0 pts: 3+ gaps named, or gap named without adjacent-strength pivot.

If context = COLD_APPLICATION:
- 10 pts: No gaps named. Letter focuses entirely on strengths.
- 5 pts: One gap hinted at but not explicitly named.
- 0 pts: Any explicit gap-naming language: "I haven't done X",
  "my experience in Y is limited", "I'll be upfront", "actively deepening",
  "ramping up on", "started ramping up", "currently learning".

# Category 7: Opening & Closing Strength (5 points)

- 2 pts: Opening sentence doesn't start with "I am..." AND mentions something
  specific to the role/company.
- 1 pt: Opening paragraph ends with a bridge to the candidate's strongest
  relevant point.
- 1 pt: Closing paragraph references something specific to the company.
- 1 pt: Sign-off is natural and brief.

# Category 8: Narrative Coherence (10 points, hard threshold = 7)

This category exists because the agent has historically dumped multiple
projects into one paragraph with no through-line. Score harshly here.

The agent committed to a strategy (provided in <strategy> tag if present):
a primary_project, an optional secondary_project, and a narrative_angle. The
letter must execute that strategy.

- 4 pts: ONE primary project is the spine. It appears in para 1 as the hook,
  is elaborated in para 2, and is referenced in para 3.
- 3 pts: At most ONE secondary project. If a secondary appears, it gets at
  most one sentence. If three or more distinct projects are named, score 0
  here regardless of strategy.
- 3 pts: The narrative_angle is recognisable in the actual letter — a reader
  could state the letter's argument in one sentence and it would match the
  committed angle.

Penalty examples:
- Para 2 cycles through 3+ projects (e.g. Company Name Resolution AND
  Sentence Transformer AND port scoring AND inverse plume dispersion): score
  0 on this category.
- The committed narrative_angle is "ML production engineering" but the
  letter actually argues "domain expertise in supply chain": score 0 or 3.

# Output schema (return EXACTLY this structure)

{
  "scores": {
    "hallucination": {"score": 0-25, "threshold_met": bool, "unsupported": []},
    "tailoring": {"score": 0-20, "threshold_met": bool, "missing_references": []},
    "voice": {"score": 0-15, "threshold_met": bool, "concerns": []},
    "banned_phrases": {"score": 0-15, "threshold_met": bool, "violations": []},
    "structure": {"score": 0-10, "concerns": []},
    "gap_handling": {"score": 0-10, "concerns": []},
    "opening_closing": {"score": 0-5, "concerns": []},
    "narrative_coherence": {"score": 0-10, "threshold_met": bool, "concerns": []}
  },
  "total": 0-110,
  "verdict": "approved" | "minor_revision" | "rewrite_required",
  "priority_fixes": ["specific fix 1", "specific fix 2"],
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
    strategy: dict | None,
) -> str:
    strategy_block = ""
    if strategy:
        strategy_block = (
            "<strategy>\n"
            f"fit_assessment: {strategy.get('fit_assessment', '?')}\n"
            f"narrative_angle: {strategy.get('narrative_angle', '?')}\n"
            f"primary_project: {strategy.get('primary_project', '?')}\n"
            f"secondary_project: {strategy.get('secondary_project') or '(none)'}\n"
            "</strategy>\n\n"
            "Verify the letter actually executes this strategy when scoring "
            "Category 8 (Narrative Coherence).\n\n"
        )
    return (
        f"<context>{context}</context>\n\n"
        f"{strategy_block}"
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
    """Pull a JSON object out of Haiku's response — tolerates stray text.

    Handles three cases: clean JSON, prose-wrapped JSON, and markdown-fenced
    JSON (```json ... ```). Tries direct parse first, then strips fences,
    then falls back to greedy {...} regex.
    """
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Strip markdown fences if present.
    fence_match = re.search(
        r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL
    )
    if fence_match:
        try:
            return json.loads(fence_match.group(1))
        except json.JSONDecodeError:
            pass

    # Greedy fallback — first { to last }.
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
            "Critic output was not valid JSON — please review the draft "
            "manually and revise for grounding, tailoring, and banned phrases."
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
    strategy: dict | None = None,
    model: str = CRITIQUE_MODEL,
) -> dict[str, Any]:
    """Score a draft. Returns the rubric result (never raises on parse errors)."""
    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=[
            {
                "type": "text",
                "text": CRITIQUE_SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[
            {
                "role": "user",
                "content": _build_critique_user_message(
                    draft=draft,
                    resume_text=resume_text,
                    job=job,
                    context=context,
                    strategy=strategy,
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

    failed = []
    for cat, s in (result.get("scores") or {}).items():
        if isinstance(s, dict) and s.get("threshold_met") is False:
            failed.append(f"{cat} ({s.get('score', '?')})")

    lines = [f"Total: {total}/110", f"Verdict: {verdict}"]
    if failed:
        lines.append("Failed thresholds: " + ", ".join(failed))
    if fixes:
        lines.append("Priority fixes:")
        for i, fix in enumerate(fixes, 1):
            lines.append(f"  {i}. {fix}")
    if notes:
        lines.append(f"Notes: {notes}")
    return "\n".join(lines)
