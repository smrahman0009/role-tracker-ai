# Role Tracker

A daily automated pipeline that fetches Canadian job postings from Adzuna, scores them against your resume using OpenAI embeddings, tailors a cover letter per top match via a multi-step LLM agent, and emails you a digest — deployed on Azure via Docker + GitHub Actions.

## Quick start (local)

```bash
# 1. Install uv (if not already)
curl -LsSf https://astral.sh/uv/install.sh | sh

# 2. Create venv and install deps
uv venv
uv pip install -e ".[dev]"

# 3. Copy and fill in secrets
cp .env.example .env

# 4. Run tests
pytest
```

## Project structure

```
src/role_tracker/   # Python package
tests/              # pytest suite
data/               # local-only (gitignored): resumes, cover letters, dedupe store
docs/               # PLAN.md and other docs
config.yaml         # job search filters
.env.example        # required environment variables (copy to .env)
pyproject.toml      # dependencies, ruff, pytest config
```

## Build phases

See [docs/PLAN.md](docs/PLAN.md) for the full phased plan (local-first, deploy-last).

| Phase | Description | Status |
|-------|-------------|--------|
| 1 | Project scaffolding | In progress |
| 2 | Adzuna client | Pending |
| 3 | Resume parsing + embedding matching | Pending |
| 4 | Cover letter tailoring (LLM agent) | Pending |
| 5 | Email digest | Pending |
| 6 | Dedupe store | Pending |
| 7 | End-to-end pipeline | Pending |
| 8 | Docker | Pending |
| 9 | Azure infrastructure | Pending |
| 10 | GitHub Actions CI/CD | Pending |
