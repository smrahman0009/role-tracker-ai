"""Load secrets from AWS Systems Manager Parameter Store at startup.

Why this exists: in production we don't want API keys baked into the
EC2 user-data, the systemd unit, or the Docker image. We want them in
SSM Parameter Store (encrypted at rest, IAM-gated, rotatable, and free
for our scale) and fetched only when the container boots.

How it integrates with pydantic-settings: rather than building a
custom settings source, we just set environment variables before
`Settings()` is instantiated. The container's startup module
(role_tracker.api.production) calls `load_secrets_into_env()` once,
and from then on every part of the app — middleware, routes, agents
— sees the keys via the same `Settings` object as in dev.

Idempotent: re-running is a no-op (env vars get overwritten with the
same value).
"""

from __future__ import annotations

import logging
import os

import boto3

logger = logging.getLogger(__name__)


def load_secrets_into_env(
    prefix: str,
    *,
    region_name: str | None = None,
    ssm_client: object | None = None,
    overwrite: bool = False,
) -> dict[str, str]:
    """Fetch every parameter under `prefix` and populate the process env.

    A parameter at `/role-tracker/ANTHROPIC_API_KEY` is set as the
    environment variable `ANTHROPIC_API_KEY` — the basename of the
    parameter path becomes the env var name.

    Args:
        prefix: SSM path prefix, e.g. "/role-tracker".
        region_name: AWS region. Defaults to whatever boto3 picks up.
        ssm_client: Optional injection point for tests (moto).
        overwrite: When False (the default), env vars that are already
            set keep their existing value. Useful in dev where a local
            `.env` should win over an accidentally-shared SSM secret.

    Returns:
        A dict of {env_var_name: value} for everything actually set
        (skipped values are not included).
    """
    if ssm_client is None:
        ssm_client = boto3.client("ssm", region_name=region_name)

    fetched: dict[str, str] = {}
    next_token: str | None = None

    while True:
        kwargs: dict[str, object] = {
            "Path": prefix,
            "Recursive": True,
            "WithDecryption": True,
            "MaxResults": 10,
        }
        if next_token:
            kwargs["NextToken"] = next_token

        response = ssm_client.get_parameters_by_path(**kwargs)

        for param in response.get("Parameters", []):
            name = param["Name"].rsplit("/", 1)[-1]
            value = param["Value"]
            if not name:
                continue
            if not overwrite and os.environ.get(name):
                logger.debug(
                    "SSM: %s already set in env, leaving as-is", name
                )
                continue
            os.environ[name] = value
            fetched[name] = value

        next_token = response.get("NextToken")
        if not next_token:
            break

    logger.info("SSM: loaded %d parameter(s) from %s", len(fetched), prefix)
    return fetched
