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

    # Gmail (deferred — email digest superseded by web app)
    gmail_sender: str = ""
    gmail_app_password: str = ""
    gmail_recipient: str = ""

    # Pipeline
    top_n_jobs: int = 5

    # Web API (Phase 5+) — bearer-token + CORS
    app_token: str = ""                          # empty disables auth in dev
    cors_origins: str = "http://localhost:5173"  # comma-separated list
    api_host: str = "127.0.0.1"
    api_port: int = 8000

    # ----- AWS / cloud-native storage backends -----
    # `file` keeps every store backed by JSON / disk (dev default).
    # `aws` swaps each store to its DynamoDB / S3 equivalent.
    # The factories in api/routes/*.py read this and pick accordingly.
    storage_backend: str = "file"

    # Region the AWS SDK should use when storage_backend == "aws".
    aws_region: str = "ca-central-1"

    # Resource names — match the values baked into infra/00-vars.sh.
    # Overridable via env vars so the same image runs in any account.
    s3_bucket: str = ""
    ddb_applied_table: str = "role-tracker-applied"
    ddb_letters_table: str = "role-tracker-letters"
    ddb_usage_table: str = "role-tracker-usage"
    ddb_queries_table: str = "role-tracker-queries"
    ddb_seen_jobs_table: str = "role-tracker-seen-jobs"
    ssm_prefix: str = "/role-tracker"


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
