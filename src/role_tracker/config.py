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

    # JSearch (RapidAPI — wraps Google for Jobs, full descriptions)
    jsearch_rapidapi_key: str = ""

    # OpenAI (embeddings for resume/job matching)
    openai_api_key: str = ""
    openai_embedding_model: str = "text-embedding-3-small"

    # Anthropic (Phase 4 — cover letter agent)
    anthropic_api_key: str = ""

    # Gmail (Phase 5 — email digest)
    gmail_sender: str = ""
    gmail_app_password: str = ""
    gmail_recipient: str = ""

    # Pipeline
    top_n_jobs: int = 5


class JobQuery(BaseModel):
    """A single job search query (used inside UserProfile too)."""

    what: str
    where: str = "canada"


class PipelineDefaults(BaseModel):
    """Pipeline-wide defaults from config.yaml — shared across users."""

    country: str = "ca"
    results_per_page: int = 20


def load_pipeline_defaults(path: Path = Path("config.yaml")) -> PipelineDefaults:
    """Parse config.yaml and return validated PipelineDefaults."""
    with open(path) as f:
        data = yaml.safe_load(f)
    return PipelineDefaults(**data["jobs"])
