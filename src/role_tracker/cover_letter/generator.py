"""Step 1 naive generator — one Sonnet 4.6 call, no tools, no critique.

This is the baseline. It's deliberately simple: we want to feel the gap
between this and the Step 3 agent (grounding, self-critique, revision).

Later steps wrap this module with an agent loop; the public
`generate_cover_letter` signature stays stable so run_match.py doesn't
need to change.
"""

from __future__ import annotations

from anthropic import Anthropic

from role_tracker.jobs.models import JobPosting
from role_tracker.users.models import UserProfile

MODEL = "claude-sonnet-4-6"
MAX_TOKENS = 1024

# Embedded as a one-shot style example. The agent should emulate voice,
# structure, and specificity — but NEVER copy facts from this letter.
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
You are an expert cover-letter writer. You write short, honest, specific letters
in the candidate's own voice.

Your job is to write ONE cover letter for the given candidate applying to the
given job. The letter is a COLD application (no referral, no prior contact).

STYLE (match the reference letter's voice):
- Warm but direct. Short sentences mixed with longer technical ones.
- Use contractions ("I've", "don't"). Start some sentences with "But", "And", "So".
- Concrete over abstract: cite real projects, technologies, and metrics from the
  resume. Do NOT use vague praise.

BANNED LANGUAGE (do not use):
- Em dashes in prose (—). Use commas or periods instead.
- LLM tell-tales: leverage (verb), navigate (verb), delve, pivotal, realm,
  showcase, cutting-edge, seamless, unleash, unlock, "at the intersection of",
  "passionate about".
- Cover-letter clichés: "I am writing to express", "I am excited/thrilled to
  apply", "I would be a great fit", "team player", "self-starter", "hit the
  ground running", "perfect candidate".

STRUCTURE:
- Header block provided by the user — put it verbatim at the top, then a blank
  line, then the greeting.
- Greeting: "Hello," (no fake first name).
- Three paragraphs:
  1. Hook that references the company and role by name, plus the single
     strongest bridge between the resume and the job.
  2. Breadth / depth. Cite concrete projects, metrics, and technologies from the
     resume that match specific requirements in the job description.
  3. Close. Because this is a cold application, do NOT explicitly name gaps
     ("I haven't done X"). Focus on strengths and ramp-up track record.
- Sign off with "Best," on its own line, then the candidate's full name.
- Total body (greeting through sign-off) must be 300–400 words.

GROUNDING:
- Every factual claim (technology, project, metric, degree, dates) must be
  directly supported by the resume text provided. If a job requirement isn't
  backed by the resume, either omit it or position an adjacent strength that IS
  in the resume.
- Never invent metrics, technologies, or experience.

Return ONLY the letter text. No preamble, no commentary, no markdown fences.
"""


def _build_user_message(
    *, user: UserProfile, resume_text: str, job: JobPosting
) -> str:
    return (
        "Write the cover letter now.\n\n"
        "Here is a reference letter from this candidate. Emulate its voice and "
        "structure — but do NOT copy facts from it; use only the resume below.\n\n"
        "<reference_letter>\n"
        f"{REFERENCE_LETTER}"
        "</reference_letter>\n\n"
        "<header_block>\n"
        f"{user.contact_header()}\n"
        "</header_block>\n\n"
        "<resume>\n"
        f"{resume_text.strip()}\n"
        "</resume>\n\n"
        "<job>\n"
        f"Title: {job.title}\n"
        f"Company: {job.company}\n"
        f"Location: {job.location}\n\n"
        f"Description:\n{job.description.strip()}\n"
        "</job>\n"
    )


def generate_cover_letter(
    *,
    user: UserProfile,
    resume_text: str,
    job: JobPosting,
    client: Anthropic,
    model: str = MODEL,
) -> str:
    """Single-shot cover letter. Returns the letter text."""
    response = client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=SYSTEM_PROMPT,
        messages=[
            {
                "role": "user",
                "content": _build_user_message(
                    user=user, resume_text=resume_text, job=job
                ),
            }
        ],
    )
    # Anthropic's response.content is a list of blocks; for a non-tool-use
    # reply there's a single TextBlock whose .text is the letter.
    return "".join(block.text for block in response.content if block.type == "text")
