"""
Dependency injection container for application services.

Extension points:
- Replace with a full-featured DI framework if needed.
- Add per-request scoped services or factories.

Example usage:
    container = build_container(Settings())
"""

from app.core.config import Settings
from app.functions.registry import FunctionRegistry
from app.functions.tools import register_builtin_tools
from app.llm_provider.factory import LLMFactory
from app.orchestration.service import OrchestrationService
from app.rag.service import RAGService
from app.scripts.executor import ScriptExecutor


class AppContainer:
    """
    Lightweight DI container that lazily constructs core services.

    Extension points:
    - Add caching, lifecycle hooks, or scoped service instances.
    - Swap implementations for testing by subclassing or composition.
    """

    def __init__(self, settings: Settings) -> None:
        """
        Initialize the container with immutable application settings.

        Extension points:
        - Add validation or derived configuration here.
        - Inject pre-built services for testing overrides.
        """

        self._settings = settings
        self._llm_factory: LLMFactory | None = None
        self._function_registry: FunctionRegistry | None = None
        self._script_executor: ScriptExecutor | None = None
        self._rag_service: RAGService | None = None
        self._orchestration_service: OrchestrationService | None = None

    @property
    def settings(self) -> Settings:
        """
        Return the application settings instance.

        Extension points:
        - Add derived settings or computed defaults on access.
        """

        return self._settings

    def llm_factory(self) -> LLMFactory:
        """
        Provide the shared LLMFactory instance.

        Extension points:
        - Add caching or custom provider setup hooks.
        """

        if self._llm_factory is None:
            self._llm_factory = LLMFactory()
        return self._llm_factory

    def function_registry(self) -> FunctionRegistry:
        """
        Provide the shared FunctionRegistry instance.

        Extension points:
        - Register external tool packs or dynamic plugins.
        """

        if self._function_registry is None:
            self._function_registry = FunctionRegistry()
            register_builtin_tools(self._function_registry)
        return self._function_registry

    def script_executor(self) -> ScriptExecutor:
        """
        Provide the ScriptExecutor instance.

        Extension points:
        - Add sandboxing or queue-backed execution here.
        """

        if self._script_executor is None:
            self._script_executor = ScriptExecutor()
        return self._script_executor

    def rag_service(self) -> RAGService:
        """
        Provide the RAGService instance.

        Extension points:
        - Swap vector store or embedding providers here.
        """

        if self._rag_service is None:
            self._rag_service = RAGService(self._settings)
        return self._rag_service

    def orchestration_service(self) -> OrchestrationService:
        """
        Provide the OrchestrationService instance.

        Extension points:
        - Wrap with tracing or per-request state management.
        """

        if self._orchestration_service is None:
            self._orchestration_service = OrchestrationService(
                llm_factory=self.llm_factory(),
                function_registry=self.function_registry(),
                script_executor=self.script_executor(),
                rag_service=self.rag_service(),
                settings=self._settings,
            )
        return self._orchestration_service


def build_container(settings: Settings) -> AppContainer:
    """
    Construct the application DI container.

    Extension points:
    - Add bootstrapping hooks or startup validations.
    """

    return AppContainer(settings)
