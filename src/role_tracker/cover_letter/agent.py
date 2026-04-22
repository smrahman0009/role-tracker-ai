"""Phase 4 Step 3 — agentic cover-letter generator.

Unlike the naive generator (Step 1), this version runs Claude in a loop with
tools. The agent decides what resume content to fetch and when it's done.

Public API:
    generate_cover_letter_agent(user=..., resume_text=..., job=..., client=...)
        → returns the saved letter text.

On error paths (agent runs too long, or finishes without saving), raises
RuntimeError with context — callers should catch and fall back to the naive
generator or log the failure.
"""

from __future__ import annotations

import copy

from anthropic import Anthropic

from role_tracker.cover_letter.tools import TOOL_SCHEMAS, build_tool_executors
from role_tracker.jobs.models import JobPosting
from role_tracker.users.models import UserProfile


def _cached_system_blocks() -> list[dict]:
    """System prompt as list-of-blocks with cache_control on the tail.

    This is the stable prefix that gets reused on every iteration of the
    agent loop, so we cache it. First call pays a small write premium;
    subsequent calls within 5 min pay ~10% of normal input cost.
    """
    return [
        {
            "type": "text",
            "text": SYSTEM_PROMPT,
            "cache_control": {"type": "ephemeral"},
        }
    ]


def _cached_tools() -> list[dict]:
    """Tool schemas with cache_control on the last one — caches the whole list."""
    tools = copy.deepcopy(TOOL_SCHEMAS)
    tools[-1]["cache_control"] = {"type": "ephemeral"}
    return tools

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 4096
MAX_ITERATIONS = 25
MAX_TOOL_CALLS = 30

# Reference letter kept here (not in generator.py) so the two modules can
# diverge independently. Style guide only — never copy facts.
REFERENCE_LETTER = """\
Hi Nick,

After you shared the ML Engineer role at ReelData AI, I took a closer look and
wanted to give you some background ahead of our Monday call. I'll be upfront: my
ML experience is in NLP and audio rather than image/video. But I think there's
real overlap. At Everstream Analytics, I fine-tuned an Audio Spectrogram
Transformer to classify vessel engine states from underwater recordings. The AST
itself is built on a vision transformer architecture that converts audio into
spectrogram representations internally, so while my input was audio data, the
underlying model shares its foundations with image classification models.

I've been working across the full ML pipeline, from data exploration and model
training through to deployment prep. I started as a software developer before
moving into data science, which means I also bring a production engineering
background that a lot of ML candidates don't have: Docker, CI/CD, Azure
Functions, microservices, and I've supported teams with Airflow and Terraform.

I haven't done edge deployment, and my PyTorch and OpenCV experience is limited.
But I've moved between NLP, audio ML, and production engineering across
different projects over the past few years, and ramping up in new domains is
something I'm used to. Looking forward to our conversation on Monday.

Best,
Shaikh Mushfikur Rahman
"""

SYSTEM_PROMPT = """\
You are an expert cover-letter writer working as an autonomous agent. You have
tools to fetch the job description and look up resume content. You must use
them — do NOT rely on memory or invent content.

PROCESS (follow in order):
1. Call read_job_description to see what the job requires.
2. Identify the 2–3 most important requirements from the JD.
3. For each requirement, call read_resume_section with a specific topic to
   find matching evidence in the candidate's resume.
4. Draft the letter in your internal working memory (do not emit it yet).
5. Call critique_draft with your draft. Read the verdict and priority fixes.
6. If verdict is "approved": call save_letter and stop.
   If verdict is "minor_revision" or "rewrite_required": revise the draft
   targeting the specific priority fixes, then call critique_draft again.
   Maximum 3 critiques total (initial + 2 revisions). After the third critique
   (or if the tool says "Max critiques reached"), call save_letter with your
   best current draft even if it is not fully approved.
7. Never call save_letter before at least one critique_draft.

RULES:
- Ground every factual claim (technology, project, metric, date) in content
  you actually retrieved via read_resume_section. Never invent.
- If the job requires something the resume lacks, do NOT fabricate it. Either
  omit that requirement or bridge to adjacent experience that IS in the resume.
- This is a COLD application (no referral). Do NOT explicitly name gaps
  ("I haven't done X", "my experience in Y is limited"). Focus on strengths.
- Use "Hello," as the greeting (no fake first name).
- Three paragraphs: hook → specific projects with metrics → close.
- 300–400 words total (header through signature).
- Sign off with "Best," on its own line, then the candidate's full name.

BANNED LANGUAGE (do not use):
- Em dashes in prose (—). Use commas or periods.
- LLM tell-tales: leverage (verb), navigate (verb), delve, pivotal, realm,
  showcase, cutting-edge, seamless, unleash, unlock, "at the intersection of",
  "passionate about".
- Cover-letter clichés: "I am writing to express", "I am excited/thrilled to
  apply", "I would be a great fit", "team player", "self-starter", "hit the
  ground running", "perfect candidate".

VOICE (match the reference letter):
- Warm but direct. Short sentences mixed with longer technical ones.
- Use contractions ("I've", "don't"). Some sentences may start with "But",
  "And", or "So".
- Concrete over abstract: specific project names, technologies, and metrics.
- Do NOT paste resume bullets verbatim. Translate them into prose.

STRUCTURE of each letter (put verbatim in the save_letter text):
1. Header block (provided in the initial message) — put at the top.
2. Blank line.
3. "Hello,"
4. Three body paragraphs.
5. "Best," on its own line.
6. Candidate's full name on the next line.
"""


def generate_cover_letter_agent(
    *,
    user: UserProfile,
    resume_text: str,
    job: JobPosting,
    client: Anthropic,
    model: str = MODEL,
    max_iterations: int = MAX_ITERATIONS,
    usage_tracker: dict | None = None,
) -> str:
    """Run the agent loop. Returns the final letter text.

    If `usage_tracker` is provided, it is populated with cache-read /
    cache-write / uncached-input token counts for the whole run. Useful for
    verifying prompt caching is working and estimating cost.
    """
    executors, state = build_tool_executors(
        resume_text=resume_text,
        job=job,
        anthropic_client=client,
    )

    goal = (
        f"Write a tailored cover letter for {user.name} applying to a "
        f"{job.title} role at {job.company}. Start by reading the job "
        "description, then fetch specific resume content, then save the "
        "final letter."
    )

    initial_user_message = (
        f"<header_block>\n{user.contact_header()}\n</header_block>\n\n"
        "<reference_letter>\n"
        "The following is an example of this candidate's writing voice. "
        "Match the style but do NOT copy facts from it.\n\n"
        f"{REFERENCE_LETTER}"
        "</reference_letter>\n\n"
        f"<candidate_name>{user.name}</candidate_name>\n\n"
        f"{goal}"
    )

    messages: list[dict] = [{"role": "user", "content": initial_user_message}]

    system_blocks = _cached_system_blocks()
    tools = _cached_tools()

    # Track cache usage across iterations so we can verify caching is working.
    cache_reads = 0
    cache_writes = 0
    uncached_input = 0

    for iteration in range(max_iterations):
        response = client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=system_blocks,
            tools=tools,
            messages=messages,
        )
        usage = getattr(response, "usage", None)
        if usage is not None:
            cache_reads += getattr(usage, "cache_read_input_tokens", 0) or 0
            cache_writes += getattr(usage, "cache_creation_input_tokens", 0) or 0
            uncached_input += getattr(usage, "input_tokens", 0) or 0
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    if state["tool_call_count"] >= MAX_TOOL_CALLS:
                        raise RuntimeError(
                            f"Agent exceeded {MAX_TOOL_CALLS} tool calls "
                            f"(iteration {iteration + 1})"
                        )
                    try:
                        result = executors[block.name](**block.input)
                    except Exception as exc:  # noqa: BLE001
                        result = f"Tool error: {exc}"
                    tool_results.append(
                        {
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result,
                        }
                    )
            messages.append({"role": "user", "content": tool_results})

            if state["saved_letter"] is not None:
                break

    if state["saved_letter"] is None:
        raise RuntimeError(
            f"Agent finished without saving a letter after {max_iterations} "
            f"iterations (tool calls: {state['tool_call_count']})"
        )

    if usage_tracker is not None:
        usage_tracker["cache_reads"] = cache_reads
        usage_tracker["cache_writes"] = cache_writes
        usage_tracker["uncached_input"] = uncached_input

    return state["saved_letter"]
