"""Config loaded from .env (secrets) and config.yaml (job search filters)."""

from pathlib import Path

import yaml
from pydantic import BaseModel
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Secrets and runtime settings — loaded from .env."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Adzuna
    adzuna_app_id: str
    adzuna_app_key: str

    # OpenAI (Phase 3 — embeddings)
    openai_api_key: str = ""

    # Anthropic (Phase 4 — cover letter agent)
    anthropic_api_key: str = ""

    # Gmail (Phase 5 — email digest)
    gmail_sender: str = ""
    gmail_app_password: str = ""
    gmail_recipient: str = ""

    # Pipeline
    top_n_jobs: int = 5


class JobQuery(BaseModel):
    """A single Adzuna search query."""

    what: str
    where: str = "canada"


class JobFilters(BaseModel):
    """Job search filters loaded from config.yaml."""

    country: str = "ca"
    results_per_page: int = 20
    queries: list[JobQuery]


def load_job_filters(path: Path = Path("config.yaml")) -> JobFilters:
    """Parse config.yaml and return validated JobFilters."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return JobFilters(**data["adzuna"])
