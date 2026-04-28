#!/usr/bin/env python3
"""Start the Role Tracker AI API in development mode.

Reads .env, then runs uvicorn with hot-reload on the configured host/port
(defaults to 127.0.0.1:8000). Production deploys use a different startup
path (gunicorn or App Service entrypoint).
"""

import uvicorn
from dotenv import load_dotenv


def main() -> None:
    load_dotenv()
    # Imported AFTER load_dotenv so Settings() picks up the env file.
    from role_tracker.config import Settings

    settings = Settings()
    print(f"\nStarting Role Tracker AI API on http://{settings.api_host}:{settings.api_port}")
    print(f"  - OpenAPI docs:   http://{settings.api_host}:{settings.api_port}/docs")
    print(f"  - Health probe:   http://{settings.api_host}:{settings.api_port}/health")
    auth_state = (
        "ENABLED" if settings.app_token else "DISABLED (dev mode)"
    )
    print(f"  - Bearer auth:    {auth_state}")
    print(f"  - CORS origins:   {settings.cors_origins}\n")

    uvicorn.run(
        "role_tracker.api.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=True,
    )


if __name__ == "__main__":
    main()
