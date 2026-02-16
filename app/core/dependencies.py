"""
FastAPI dependency providers for core services.

Extension points:
- Add request-scoped overrides or testing hooks.
- Provide per-tenant settings or container instances.

Example usage:
    Depends(get_orchestration_service)
"""

from functools import lru_cache

from app.core.config import Settings
from app.core.container import AppContainer, build_container
from app.functions.registry import FunctionRegistry
from app.orchestration.service import OrchestrationService
from app.rag.service import RAGService


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """
    Load and cache application settings.

    Extension points:
    - Add validation hooks or computed defaults.
    """

    return Settings()


@lru_cache(maxsize=1)
def get_container() -> AppContainer:
    """
    Build and cache the application DI container.

    Extension points:
    - Add startup diagnostics or health checks.
    """

    return build_container(get_settings())


def get_orchestration_service() -> OrchestrationService:
    """
    Provide the OrchestrationService dependency.

    Extension points:
    - Replace with a per-request instance if needed.
    """

    return get_container().orchestration_service()


def get_rag_service() -> RAGService:
    """
    Provide the RAGService dependency.

    Extension points:
    - Swap for a mock implementation in tests.
    """

    return get_container().rag_service()


def get_function_registry() -> FunctionRegistry:
    """
    Provide the FunctionRegistry dependency.

    Extension points:
    - Add dynamic tool discovery based on tenant context.
    """

    return get_container().function_registry()
