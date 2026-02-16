"""
FastAPI application entrypoint for the LLM orchestration platform.

Extension points:
- Add middleware, exception handlers, and startup/shutdown hooks.
- Register additional routers and dependency overrides for testing.
- Replace the DI container with a more advanced provider if needed.

Example usage:
    uvicorn app.main:app --reload
"""

from fastapi import FastAPI

from app.api.router import api_router


def create_app() -> FastAPI:
    """
    Create and configure the FastAPI application instance.

    Extension points:
    - Attach middleware and instrumentation.
    - Override dependencies for testing or staging.
    - Add additional routers for new domains.
    """

    app = FastAPI(title="LLM Orchestration Platform", version="0.1.0")
    app.include_router(api_router)
    return app


app = create_app()
