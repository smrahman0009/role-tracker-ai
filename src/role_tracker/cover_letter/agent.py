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
You are an expert cover-letter writer working as an autonomous agent. Your
goal is ONE focused, honest letter — not a project dump. You write as a real
human writer would: pick one thread, commit, edit ruthlessly.

MANDATORY PROCESS (you cannot save without doing all five phases in order):

PHASE 1 — UNDERSTAND THE ROLE
- Call read_job_description.
- Identify the 2 or 3 most important requirements.

PHASE 2 — UNDERSTAND THE CANDIDATE
- Call read_resume_section 2 to 4 times. Look for evidence supporting (or
  failing to support) the requirements you identified.
- Be honest about what is NOT in the resume. Soft hedges like "familiar with",
  "exposure to", "informally applied" still count as factual claims and
  must be backed by resume content.

PHASE 3 — STRATEGY (CRITICAL)
- Call commit_to_strategy. You must:
  * Give an honest fit_assessment (HIGH / MEDIUM / LOW).
  * Pick ONE primary project as the spine of the letter.
  * Pick AT MOST ONE secondary project. Often zero is better than one.
  * Write a one-sentence narrative_angle that ties candidate-to-role.
- DO NOT pick a project just because it has overlapping keywords. Pick the
  one whose CORE IDEA most closely maps to the role's core idea.
- For LOW fit: pick the closest adjacent strength as primary, and write the
  letter honestly. Do not strain to seem qualified.

PHASE 4 — DRAFT, CRITIQUE, REVISE
- Draft the letter following the structure below.
- Call critique_draft. Read the verdict and priority fixes carefully.
- If verdict is "approved": move to PHASE 5.
- Otherwise: revise targeting the priority fixes, then critique again.
- Maximum 3 critiques. After the third (or "Max critiques reached"), move on.

PHASE 5 — SAVE
- Call save_letter. The system runs deterministic checks (word count,
  paragraph length). If it rejects, fix the specific issues and retry.

LETTER STRUCTURE (put verbatim in save_letter text):
1. Header block (provided in the initial message).
2. Blank line.
3. Greeting: "Dear {Company} Team," — substitute the actual company name
   from the JD (e.g., "Dear Acme Team,"). If the company name is awkward
   to pair with "Team" (e.g., contains "Inc." / "Corporation" / a comma /
   already ends in "Team"), use "Dear Hiring Team," instead. Never use
   "Hello," or "To whom it may concern,".
4. Body paragraphs (see below).
5. "Best," on its own line.
6. Candidate's full name on the next line.

BODY PARAGRAPHS — three of them, each with a job:
- Paragraph 1 (hook, 60-90 words): Reference the company name and exact role.
  Introduce the PRIMARY project and the narrative angle in plain language.
  Do NOT list multiple projects here.
- Paragraph 2 (elaboration, 100-130 words): Tell the story of the primary
  project — what was broken, what you built, what changed. Use ONE specific
  metric. If a secondary project exists, mention it in ONE sentence to
  reinforce the angle. Do NOT list a third project.
- Paragraph 3 (close, 50-80 words): Connect the primary project's lesson to
  what the company specifically does. Keep it short.

GROUNDING (zero tolerance):
- Every factual claim must come from content you retrieved via
  read_resume_section. This includes hedged claims.
- If the JD requires X and the resume lacks X, do not write "I'm familiar
  with X" or "I've informally applied X". These read as bluffs.
- For LOW fit roles, set fit_assessment="LOW" and write an honest letter
  that does not pretend the gap doesn't exist.

COLD APPLICATION RULES:
- Do NOT explicitly name gaps ("I haven't done X", "I'll be upfront",
  "actively deepening", "ramping up"). Focus on the strengths you DO have.
- Sign off with "Best,".
- Length: 300-400 words total. Hard ceiling 420.

BANNED LANGUAGE:
- Em dashes in prose. Use commas or periods.
- LLM tell-tales: leverage (verb), navigate (verb), delve, pivotal, realm,
  showcase, cutting-edge, seamless, unleash, unlock, "at the intersection of",
  "passionate about".
- Cover-letter clichés: "I am writing to express", "I am excited/thrilled to
  apply", "I would be a great fit", "team player", "self-starter", "hit the
  ground running", "perfect candidate".

VOICE:
- Warm but direct. Mix short sentences (<12 words) with longer technical ones.
- Use contractions ("I've", "don't"). Some sentences may start with "But",
  "And", or "So".
- Concrete over abstract. Translate resume bullets into prose, do not paste.
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
    instruction: str | None = None,
    template: str | None = None,
    extended_thinking: bool = False,
) -> str:
    """Run the agent loop. Returns the final letter text.

    Optional steering inputs from the GenerateLetterDialog
    (docs/cover_letter_dialog_plan.md):

    - `instruction`: free-text guidance from the user ("make it punchy,
      lead with the LLM project"). Woven into the initial user
      message as high-priority guidance.
    - `template`: an existing letter to mirror in voice, length, and
      structure. Content stays grounded in this resume + JD; only
      style is borrowed.
    - `extended_thinking`: when True, every Anthropic call gets a
      thinking budget. ~2-3× cost and latency; better quality on
      non-obvious resume↔JD matches.

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

    # User-supplied template (from the Generate dialog) replaces the
    # baked-in REFERENCE_LETTER style guide when present. Same
    # contract: copy STYLE not facts.
    style_sample = template if template else REFERENCE_LETTER

    steering_block = ""
    if instruction:
        steering_block = (
            "\n\n<user_instruction>\n"
            "The candidate has provided high-priority steering for "
            "this letter. Treat it as guidance, but do NOT invent "
            "experience to satisfy it — if a request can't be honoured "
            "with what's actually in the resume, push back politely "
            "in the strategy commit step.\n\n"
            f"{instruction.strip()}\n"
            "</user_instruction>"
        )

    initial_user_message = (
        f"<header_block>\n{user.contact_header()}\n</header_block>\n\n"
        "<reference_letter>\n"
        "The following is an example of this candidate's writing voice. "
        "Match the style but do NOT copy facts from it.\n\n"
        f"{style_sample}"
        "</reference_letter>\n\n"
        f"<candidate_name>{user.name}</candidate_name>\n\n"
        f"{goal}"
        f"{steering_block}"
    )

    messages: list[dict] = [{"role": "user", "content": initial_user_message}]

    system_blocks = _cached_system_blocks()
    tools = _cached_tools()

    # Track cache usage across iterations so we can verify caching is working.
    cache_reads = 0
    cache_writes = 0
    uncached_input = 0

    # Anthropic's extended thinking burns thinking-tokens that are
    # billed separately; budget chosen to give meaningful headroom
    # without ballooning per-call cost. Only attached when requested.
    extra_kwargs: dict = {}
    # Anthropic requires max_tokens > thinking.budget_tokens. When
    # thinking is enabled we must lift the per-call output ceiling
    # accordingly; the actual completion still stops when the model
    # is done, so this doesn't make the response itself larger or
    # more expensive.
    THINKING_BUDGET = 10_000
    effective_max_tokens = MAX_TOKENS
    if extended_thinking:
        effective_max_tokens = THINKING_BUDGET + MAX_TOKENS
        extra_kwargs["thinking"] = {
            "type": "enabled",
            "budget_tokens": THINKING_BUDGET,
        }

    for iteration in range(max_iterations):
        response = client.messages.create(
            model=model,
            max_tokens=effective_max_tokens,
            system=system_blocks,
            tools=tools,
            messages=messages,
            **extra_kwargs,
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
        usage_tracker["strategy"] = state.get("strategy")
        usage_tracker["last_critique"] = state.get("last_critique")

    return state["saved_letter"]
