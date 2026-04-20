# Agentic AI — Beginner-to-Mid-Level Tutorial

> A practical course using the Role Tracker AI project as the running example.
> Every concept is paired with code you'd actually write in Phase 4 (cover-letter generation).

---

## Table of Contents

1. [What "agentic" really means](#1-what-agentic-really-means)
2. [The mental model: LLM as the CPU, tools as the instruction set](#2-the-mental-model)
3. [Your first LLM call (not yet an agent)](#3-your-first-llm-call)
4. [Tools — teaching Claude to ask for things](#4-tools)
5. [The agent loop — the heart of everything](#5-the-agent-loop)
6. [A minimal agent for our project — cover-letter v1](#6-minimal-agent-v1)
7. [Prompt engineering for agents (system prompts that work)](#7-prompt-engineering)
8. [Self-critique and revision — making letters actually good](#8-self-critique)
9. [Multi-step planning and decomposition](#9-planning)
10. [Memory — short-term vs long-term](#10-memory)
11. [Cost, latency, and prompt caching](#11-cost)
12. [Safety rails — stopping runaway agents](#12-safety)
13. [Evaluating agents (how do you know it's good?)](#13-eval)
14. [Where to go next (mid-level and beyond)](#14-next)

---

## 1. What "agentic" really means

A **regular program** follows a sequence you wrote:

```python
resume = parse_resume(path)
jobs = fetch_jobs()
ranked = rank_by_similarity(resume, jobs)
print(ranked[:5])
```

You decided every step. The computer just obeys. This is all of Phase 1-3 of our project.

An **agentic** program hands the decision-making to an LLM:

```python
agent.run(goal="Write a great cover letter for this job")
# Agent decides: read resume? read job again? draft? critique? revise? done?
```

The LLM is given a **goal**, a set of **tools**, and a **loop**, and it decides what to do next on every iteration until it judges the goal achieved.

The one-line definition I want you to remember:

> **An agent is an LLM running in a loop, using tools to accomplish a goal it was given.**

Three pieces matter here:
- **Loop** — it runs more than once; each iteration the LLM sees everything that happened and decides the next step.
- **Tools** — concrete capabilities (read a file, call an API, save output) the LLM can invoke.
- **Goal** — described in natural language, not code. The LLM translates it into actions.

### Why this is a big deal

For 50 years, software has been "human writes every step, computer executes." Agentic software flips that: **the human describes the outcome, the LLM figures out the steps**. That's a fundamentally different contract with the computer. It unlocks tasks that were previously impossible to automate because they required judgment — tasks like "write a cover letter tailored to this job," which has no algorithmic definition of "good."

---

## 2. The mental model

Here is the single most useful mental model for agents:

> **The LLM is a CPU. Tools are the instruction set. The agent loop is the fetch-decode-execute cycle.**

In a real CPU:
- The CPU can only do what its instruction set allows (ADD, LOAD, JUMP, etc.).
- It runs a loop: fetch next instruction → decode it → execute → repeat.
- State lives in registers and memory.

In an agent:
- The LLM can only act through tools you give it (`read_resume`, `save_letter`, etc.).
- It runs a loop: read context → decide next tool call → execute → repeat.
- State lives in the conversation history (every message and tool result so far).

This model predicts everything:
- **"What can my agent do?"** → Whatever tools you gave it. Nothing more.
- **"Why did my agent loop forever?"** → No `halt` instruction. You must give it a way to stop (and a max iteration cap as a safety net).
- **"Why did it forget what it did?"** → It only remembers what's in the conversation history.

Keep this in mind for every section below.

---

## 3. Your first LLM call

Before agents, you need to be fluent with a single LLM call. This is one API request, one response. No loop, no tools.

### In our project's context

Imagine the simplest possible cover-letter feature. No agent. Just:

```python
# scripts/prototype_letter.py — NOT the final design, just for learning
from anthropic import Anthropic

client = Anthropic()  # reads ANTHROPIC_API_KEY from env

resume_text = open("data/resumes/smrah.txt").read()
job_description = "We're hiring an ML engineer at Shopify..."

response = client.messages.create(
    model="claude-opus-4-7",
    max_tokens=1024,
    messages=[
        {
            "role": "user",
            "content": (
                f"Write a cover letter for this job.\n\n"
                f"RESUME:\n{resume_text}\n\n"
                f"JOB:\n{job_description}"
            ),
        }
    ],
)

print(response.content[0].text)
```

This works. It will produce a cover letter. And it'll be **mediocre** — generic phrasing, vague claims, nothing the candidate couldn't have written themselves.

Why mediocre? Because:
- Claude sees *everything* you stuffed into the prompt. If your resume is 2000 words and the job is 800 words, Claude has to synthesize all of it in one pass.
- Claude can't go back and verify — "wait, does the resume actually mention PyTorch?" — it just has to trust its first read.
- Claude can't self-check — one shot, done.

Understand this limitation deeply, because **this is the exact pain that agents fix.**

### Key terms from this code

- **`messages=[...]`** — the conversation history. A list of `{role, content}`. Role is `user` or `assistant`.
- **`max_tokens`** — upper cap on output length. ~4 characters per token, so 1024 tokens ≈ 4000 characters ≈ a long cover letter.
- **`model`** — which Claude to use. `claude-opus-4-7` is most capable; `claude-sonnet-4-6` is a cheaper mid-tier; `claude-haiku-4-5-20251001` is cheapest/fastest.

---

## 4. Tools

A **tool** is a capability you expose to the LLM. The LLM never runs it — it emits a structured request "please call `read_resume_section` with `topic='machine learning'`," and your Python code actually runs it and hands back the result.

### Anatomy of a tool

Every tool has three parts:

```python
tool_definition = {
    "name": "read_resume_section",
    "description": (
        "Return the part of the candidate's resume that matches a topic. "
        "Use this to find specific experience instead of reading the whole resume."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "topic": {
                "type": "string",
                "description": "The topic to search for, e.g. 'NLP', 'leadership', 'Python'",
            }
        },
        "required": ["topic"],
    },
}
```

**Three parts:**
1. **`name`** — how Claude refers to it.
2. **`description`** — the *most important* field. Claude reads this to decide whether to use the tool. Write it like a docstring aimed at a smart colleague. Bad descriptions are the #1 reason agents misbehave.
3. **`input_schema`** — JSON Schema describing the arguments. Claude will fill this in when calling the tool.

### And the Python side — the tool executor

```python
def read_resume_section(topic: str) -> str:
    """Actual implementation — runs when Claude requests this tool."""
    # In real Phase 4 code, this would be an embedding-similarity lookup
    # against chunks of the resume. For tutorial purposes:
    resume = open("data/resumes/smrah.txt").read()
    # naive: return paragraphs containing any topic keyword
    paragraphs = resume.split("\n\n")
    matching = [p for p in paragraphs if topic.lower() in p.lower()]
    return "\n\n".join(matching) or f"No resume content found for topic: {topic}"
```

Claude never sees the implementation. It only sees the `description` and `input_schema`. This is critical — it means you can change your implementation (switch from keyword search to embedding search) without retraining or re-prompting Claude.

### Tools for our cover-letter agent (Phase 4 roadmap)

Here's the full toolkit I'd give the Phase 4 agent:

| Tool | Purpose | Implementation |
|---|---|---|
| `read_job_description()` | Claude can re-read the job when needed | Return stored string |
| `read_resume_section(topic)` | On-demand resume lookup | Keyword or embedding search |
| `list_resume_topics()` | Claude discovers what's in the resume | Return headings/sections |
| `draft_paragraph(purpose, content)` | Track drafted paragraphs | Append to in-memory list |
| `critique_draft(full_letter)` | Self-evaluation with rubric | Another Claude call with scoring prompt |
| `save_letter(text)` | Finalize | Write to `data/cover_letters/...` |

Notice: each tool has **one clear purpose**. Don't build mega-tools like `do_cover_letter_stuff(action, args)` — LLMs get confused by polymorphic tools.

---

## 5. The agent loop

This is where everything comes together. The agent loop is what makes it an *agent* instead of a fancy function call.

### The bare-bones loop

```python
def run_agent(goal: str, tools: list[dict], tool_fns: dict[str, callable]) -> str:
    """Run an agent until it returns a final answer or hits the iteration cap."""
    messages = [{"role": "user", "content": goal}]
    max_iterations = 15

    for i in range(max_iterations):
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            tools=tools,
            messages=messages,
        )

        # Append Claude's reply to history (including any tool calls it made)
        messages.append({"role": "assistant", "content": response.content})

        # Case 1: Claude is done. No tool calls. Return the text.
        if response.stop_reason == "end_turn":
            return extract_text(response.content)

        # Case 2: Claude requested one or more tool calls. Execute them.
        if response.stop_reason == "tool_use":
            tool_results = []
            for block in response.content:
                if block.type == "tool_use":
                    result = tool_fns[block.name](**block.input)
                    tool_results.append({
                        "type": "tool_result",
                        "tool_use_id": block.id,
                        "content": result,
                    })
            messages.append({"role": "user", "content": tool_results})
            # Loop continues — Claude sees the tool results next iteration

    raise RuntimeError(f"Agent exceeded {max_iterations} iterations")
```

Read that slowly. It's *the entire pattern.* Every agent framework (LangChain, LangGraph, AutoGen, Agent SDK) is a fancier version of this exact loop.

### What happens at each iteration

1. **Claude receives the full conversation** — every message, every tool call, every tool result.
2. **Claude decides.** Either: (a) this is enough, produce final text, stop; or (b) call one or more tools.
3. **Your code runs any tools** and appends results to the conversation.
4. **Repeat.**

### Concrete trace for our project

User goal:
> "Write a tailored cover letter for a Staff ML Engineer role at Shopify. Resume is accessible via tools."

Possible agent trace:

```
Iteration 1:
  Claude: "I'll start by reading the job description."
  Tool call: read_job_description()
  Result: "Staff ML Engineer at Shopify. Ranking, recommendations, PyTorch..."

Iteration 2:
  Claude: "Job emphasizes PyTorch and recommender systems. Let me check resume."
  Tool call: read_resume_section(topic="PyTorch")
  Result: "Built production PyTorch models for..."

Iteration 3:
  Claude: "Good. Let me also check for recommender work."
  Tool call: read_resume_section(topic="recommender systems")
  Result: "No resume content found for topic: recommender systems"

Iteration 4:
  Claude: "No direct recsys experience — I'll emphasize ranking models instead."
  Tool call: read_resume_section(topic="ranking")
  Result: "Learning-to-rank model for search relevance..."

Iteration 5:
  Claude drafts the letter. Calls critique_draft().
  Result: "Score 7/10. Missing concrete metrics."

Iteration 6:
  Claude revises, adds "improved NDCG by 12%" from the resume.
  Calls critique_draft() again. Score 9/10.

Iteration 7:
  Claude: "Saving final version."
  Tool call: save_letter(text="...")
  Result: "Saved to data/cover_letters/smrah/shopify_staff_ml.md"

Iteration 8:
  Claude: "Done. Letter saved."
  stop_reason: "end_turn"
  → return.
```

That's an agent. Eight iterations, six tool calls, Claude decided every step.

---

## 6. Minimal agent v1

Let's design the *simplest* useful version for Phase 4 — two tools, no self-critique yet.

```python
# src/role_tracker/agents/cover_letter.py — Phase 4 v1
from anthropic import Anthropic
from pathlib import Path

TOOLS = [
    {
        "name": "read_resume_section",
        "description": (
            "Fetch the part of the candidate's resume matching a topic. "
            "Prefer this over trying to recall the resume from memory. "
            "Example topics: 'machine learning', 'leadership', 'Python'."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"topic": {"type": "string"}},
            "required": ["topic"],
        },
    },
    {
        "name": "save_letter",
        "description": (
            "Save the final cover letter and end the task. "
            "Only call this once you are confident the letter is tailored and specific."
        ),
        "input_schema": {
            "type": "object",
            "properties": {"text": {"type": "string"}},
            "required": ["text"],
        },
    },
]


def build_tool_fns(resume_text: str, output_path: Path):
    saved = {"value": None}

    def read_resume_section(topic: str) -> str:
        paragraphs = resume_text.split("\n\n")
        matches = [p for p in paragraphs if topic.lower() in p.lower()]
        return "\n\n".join(matches) or f"No content found for: {topic}"

    def save_letter(text: str) -> str:
        output_path.write_text(text)
        saved["value"] = text
        return f"Saved to {output_path}"

    return {"read_resume_section": read_resume_section, "save_letter": save_letter}, saved


def generate_cover_letter(
    *, resume_text: str, job_description: str, output_path: Path, api_key: str
) -> str:
    client = Anthropic(api_key=api_key)
    tool_fns, saved = build_tool_fns(resume_text, output_path)

    system = (
        "You are a professional cover-letter writer. Write a tailored, specific, "
        "1-page letter. Ground every claim in the actual resume content — use "
        "read_resume_section to look things up. Never invent experience. "
        "When done, call save_letter."
    )
    goal = f"Write a cover letter for this job:\n\n{job_description}"

    messages = [{"role": "user", "content": goal}]
    for _ in range(15):
        response = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=4096,
            system=system,
            tools=TOOLS,
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        if response.stop_reason == "end_turn":
            break

        tool_results = []
        for block in response.content:
            if block.type == "tool_use":
                result = tool_fns[block.name](**block.input)
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": result,
                })
        messages.append({"role": "user", "content": tool_results})

    if saved["value"] is None:
        raise RuntimeError("Agent finished without saving a letter")
    return saved["value"]
```

That's ~50 lines of real agent code. It will run, produce a tailored cover letter, and ground claims in your actual resume.

---

## 7. Prompt engineering for agents

The **system prompt** is how you steer an agent without writing code. Think of it as the agent's job description and code of conduct.

### Anatomy of a good agent system prompt

```
You are a [role].

Your task is to [goal — clear, single outcome].

You have access to these tools: [brief overview, though Claude already sees full schemas].

RULES:
- [Explicit do's]
- [Explicit don'ts]

PROCESS:
- Step 1: [first expected move]
- Step 2: [next]
- ...

OUTPUT:
- [What the final output looks like / how you know you're done]
```

### For our cover-letter agent, a stronger prompt:

```
You are an expert cover-letter writer for tech roles.

Your task is to write a one-page cover letter tailored to a specific job, using
only claims supported by the candidate's actual resume.

RULES:
- Ground every skill claim in the resume. Use read_resume_section to verify.
- Never invent experience. If the resume lacks something the job requires,
  either omit it or honestly position adjacent experience.
- Prefer specific metrics ("improved X by Y%") over generic praise ("great team player").
- Write in the candidate's voice — professional, warm, confident, not flowery.

PROCESS:
1. Identify the 3 most important requirements in the job description.
2. For each, look up matching resume content with read_resume_section.
3. Draft the letter with a hook, 2-3 body paragraphs (one per requirement), and a close.
4. Review for specificity. If any paragraph feels generic, revise.
5. Call save_letter with the final text.

The letter should be 300-400 words, no more.
```

### Prompt principles for agents (general)

- **Be explicit about when to stop.** LLMs hate uncertainty. "Call save_letter only when you're done revising."
- **Tell it which tools to use first.** Reduces wasted iterations.
- **Use capitalized section headers.** `RULES:`, `PROCESS:` — LLMs attend to these strongly.
- **Concrete > abstract.** "Letters should have metrics" beats "letters should be specific."
- **Anti-patterns matter.** Telling it what *not* to do is often more effective than telling it what to do.

---

## 8. Self-critique

Single-shot letters are mediocre. The biggest quality jump comes from letting the agent critique its own draft.

### The pattern

Add a `critique_draft` tool that calls Claude (or a cheaper model) with a scoring rubric:

```python
def critique_draft(draft: str) -> str:
    """Score a cover letter against a rubric. Used by the main agent for self-revision."""
    rubric_prompt = f"""
    Score this cover letter on four dimensions, 1-10 each, with one-sentence justifications:

    1. SPECIFICITY — does it cite concrete projects, metrics, technologies?
    2. RELEVANCE — does it address the actual job requirements?
    3. VOICE — does it sound like a real person, not a template?
    4. CONCISENESS — is it ≤ 400 words with no filler?

    End with: OVERALL: [score]/40. VERDICT: [ship | revise].

    LETTER:
    {draft}
    """
    response = client.messages.create(
        model="claude-haiku-4-5-20251001",  # cheap model for scoring
        max_tokens=512,
        messages=[{"role": "user", "content": rubric_prompt}],
    )
    return response.content[0].text
```

Add this to the agent's tool list, and the system prompt gets:

> "After drafting, call `critique_draft`. If the score is below 32/40 or verdict is 'revise', produce a revised draft and critique again. Stop revising after 3 attempts."

This is your first **multi-agent** pattern — the main agent uses a cheaper "judge" agent as a tool. Extremely common in production systems.

### Why this works

Claude is better at *evaluating* text than *generating* perfect text on the first try. Self-critique exploits this. It also separates concerns: the drafting prompt doesn't need to encode the rubric, because the critique does.

---

## 9. Planning

For cover letters, a linear plan works. But for more complex tasks — "apply to these 20 jobs and track which need follow-up" — you need **explicit planning**.

### The "plan first, then execute" pattern

```
Iteration 1-2: Agent produces a plan (list of steps).
Iteration 3+: Agent executes the plan step by step, marking each done.
```

Add two tools:

```python
{"name": "write_plan", "description": "Write a numbered plan before starting work.", ...}
{"name": "mark_step_done", "description": "Mark a plan step complete before moving on.", ...}
```

System prompt:
> "Start by calling `write_plan` with your approach. Then execute each step in order, calling `mark_step_done` after each. Revise the plan only if a step reveals new information."

### Why explicit planning helps

- **Transparency** — you can log the plan and debug why the agent went sideways.
- **Focus** — forces the agent to commit to an approach instead of oscillating.
- **Resumability** — if the agent crashes on step 3, you can resume from the saved plan.

We probably *don't* need this for Phase 4 (cover letters are simple enough), but it's worth knowing for Phase 5 if we build a full job-application agent.

---

## 10. Memory

### Short-term memory (within a run)

The conversation history **is** the agent's short-term memory. Everything it said, every tool result — all of it is in context next iteration.

**Important limit:** context is finite (200K tokens for Claude Opus 4.7, but each token costs money and adds latency). A 20-iteration agent with large tool results can blow past useful context fast.

Mitigations:
- Keep tool results short. `read_resume_section` should return 200 words, not 2000.
- Summarize periodically: "Here's what you've learned so far: [short summary]" — replace old messages with a summary.
- Use cheap-model "compaction": a secondary LLM call that compresses the history.

### Long-term memory (across runs)

If the agent needs to remember things between runs — e.g. "we already wrote a letter for this job last week, don't redo it" — you need storage *outside* the conversation.

Options, from simplest to fanciest:
1. **A file** — `data/cover_letters/{user}/log.jsonl` with one line per letter generated.
2. **A SQLite database** — queryable by job_id.
3. **A vector store** — semantic search over past outputs ("find letters similar to this job").

For Phase 4, a JSONL log is plenty. No vector DB until you actually need it.

---

## 11. Cost

Agents multiply API costs because they make multiple calls per task. Here's how to think about it.

### Per-iteration cost

Each iteration is one `messages.create` call. Its cost depends on:
- **Input tokens** — the entire history so far. Grows every iteration.
- **Output tokens** — what Claude produces this turn.

A 10-iteration agent with a 2000-token resume in context: roughly **150K total input tokens** across all iterations (because the history is re-sent every time), plus **~5K output tokens**.

At Opus 4.7 pricing (rough order of magnitude — check current docs):
- 150K input × $15/M = ~$2.25
- 5K output × $75/M = ~$0.38
- **≈ $2.50 per cover letter**

For 5 letters/day, that's $12.50/day, $375/month. Not free.

### Prompt caching — the single most important cost optimization

Anthropic supports **prompt caching**: you mark prefix parts of your messages as cacheable, and re-use over subsequent calls gets billed at ~10% of the regular input price. The cache has a 5-minute TTL by default.

For our agent, the **system prompt and resume** are identical on every iteration. Caching them cuts input costs by ~90%.

```python
response = client.messages.create(
    model="claude-opus-4-7",
    system=[
        {
            "type": "text",
            "text": full_system_prompt_with_resume_included,
            "cache_control": {"type": "ephemeral"},  # ← this
        }
    ],
    # ... rest unchanged
)
```

You must pass system as a list-of-blocks (not a string) to use caching. Mark stable prefixes as cached.

### Model choice

- **Use Opus for the main agent loop** (it's the "brain" making decisions — worth it).
- **Use Haiku for sub-tasks** like scoring, summarizing, embedding fallbacks (10x+ cheaper).

This "heterogeneous model" pattern is standard in production.

---

## 12. Safety

Agents can go wrong. Here are the core defenses.

### 1. Iteration cap
Already shown. `max_iterations = 15`. If the agent hits it without finishing, raise.

### 2. Tool-call budget
Separately cap total tool calls (e.g. 30). Prevents one iteration from calling 50 tools.

### 3. Validate tool inputs
Don't trust Claude's tool arguments blindly. If `save_letter(path=...)` accepts a path, make sure it's inside `data/cover_letters/`, not `/etc/passwd`.

```python
def save_letter(text: str) -> str:
    # Path is hard-coded, not Claude-provided — safer
    output_path.write_text(text)
```

### 4. Dry-run mode
Let users preview the agent's planned actions before executing irreversible ones. Not critical for cover letters (saving a file is reversible); essential for agents that send emails or spend money.

### 5. Logging
Log every tool call and every model response. When an agent misbehaves, the log is the only way to debug. Plain JSON lines work:

```python
# data/agent_logs/2026-04-19_smrah_shopify.jsonl
{"iter": 1, "type": "tool_call", "name": "read_resume_section", "input": {...}}
{"iter": 1, "type": "tool_result", "content": "..."}
{"iter": 2, "type": "final", "text": "..."}
```

### 6. Sanity check the output
For cover letters specifically: word count, no obvious hallucinations (e.g. cross-check claimed skills against resume), profanity filter. Belt-and-suspenders.

---

## 13. Evaluating agents

"The agent seems to work" is not a strategy. You need to measure it.

### Golden set evaluation

Build a small fixed set of (resume, job) pairs — 10-20 is plenty to start — with **expected characteristics**:
- "Letter should mention PyTorch" (because resume + job both have it)
- "Letter should NOT claim Rust experience" (resume has none)
- "Letter should be 300-400 words"

Run the agent on each. Score pass/fail per criterion. Track over time.

```python
# tests/agents/test_cover_letter_golden.py
def test_letter_mentions_expected_skills():
    letter = generate_cover_letter(...)
    assert "PyTorch" in letter
    assert "Rust" not in letter  # not in resume
    assert 250 < len(letter.split()) < 450
```

### LLM-as-judge

For subjective quality ("is this letter *good*?"), use another Claude call to score. Same rubric as `critique_draft`, applied to a batch of letters. Track average score over time.

### A/B testing

When you change the prompt or add a tool, run both versions on the golden set. Compare. Only ship the change if scores go up.

### What "mid-level" looks like

Getting an agent working for one example is beginner. **Building an eval loop that lets you iterate on the agent confidently** is mid-level. Spend time here. It's the difference between "cool demo" and "shippable system."

---

## 14. Where to go next

You've covered the fundamentals. Mid-level territory starts here:

- **Multi-agent systems** — a "planner" agent that dispatches to "worker" agents. Useful when your task has multiple distinct phases (e.g. "research company → draft letter → critique → save").
- **Retrieval-augmented generation (RAG)** — embedding-based retrieval wired into tools. We already do resume embedding in Phase 3; a natural Phase 5 extension would be `read_resume_section` using semantic search.
- **Tool composition** — tools that call other tools. E.g. `draft_paragraph` internally calls `read_resume_section` then Claude. Keeps agent traces shorter.
- **Structured outputs / JSON mode** — force Claude to return JSON matching a schema. Great for pipelines where the output feeds another system.
- **Streaming** — get tokens as they generate instead of waiting for full response. Better UX for interactive tools.
- **Computer use / browser agents** — Claude can control a real browser. Overkill for Role Tracker AI, but you'll see it everywhere in 2026.
- **Agent frameworks** — LangGraph, AutoGen, Anthropic's Agent SDK. Worth learning *after* you've built an agent from scratch — otherwise you won't understand what the framework is hiding.

---

## Summary — the one-page cheat sheet

- **Agent = LLM + tools + loop.**
- **Tools** are capabilities you define with a name, description, and input schema. Claude never runs them — your code does, and hands results back.
- **The loop** runs until Claude produces `end_turn` or you hit an iteration cap.
- **System prompts** are the agent's job description — be explicit about rules, process, and stopping conditions.
- **Self-critique** is the single biggest quality lever — let the agent score and revise its own drafts.
- **Prompt caching** is the single biggest cost lever — cache the stable prefix.
- **Eval loops** are the single biggest iteration lever — without them you can't know if changes help.

You now know enough to build, ship, and improve a real agent. In Phase 4, we're going to build exactly the one described in section 6 — then upgrade it through sections 7 and 8 as you're ready.
