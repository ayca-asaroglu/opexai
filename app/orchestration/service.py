"""
Orchestration service that builds and runs flow definitions.

Extension points:
- Add graph validation and branching semantics.
- Add observability hooks and execution telemetry.
"""

from app.core.config import Settings
from app.functions.registry import FunctionRegistry
from app.llm_provider.factory import LLMFactory
from app.llm_provider.models import LLMProviderConfig
from app.models.flow import FlowRunRequest, FlowRunResponse
from app.orchestration.graph import build_flow_graph, build_initial_state
from app.rag.service import RAGService
from app.scripts.executor import ScriptExecutor


class OrchestrationService:
    """
    Build and execute orchestration flows from API requests.

    Extension points:
    - Add flow persistence or versioning support.
    - Add policy enforcement and access control.
    """

    def __init__(
        self,
        llm_factory: LLMFactory,
        function_registry: FunctionRegistry,
        script_executor: ScriptExecutor,
        rag_service: RAGService,
        settings: Settings,
    ) -> None:
        """
        Initialize the service with dependencies.

        Extension points:
        - Inject tracing or metrics collectors.
        """

        self._llm_factory = llm_factory
        self._function_registry = function_registry
        self._script_executor = script_executor
        self._rag_service = rag_service
        self._settings = settings
        self._graph = None

    def run_flow(self, request: FlowRunRequest) -> FlowRunResponse:
        """
        Execute a flow run request and return the final response.

        Extension points:
        - Add per-node overrides and runtime configuration merging.
        """

        graph = self._get_graph()
        initial_state = build_initial_state(request.input)
        result_state = graph.invoke(initial_state)

        answer = result_state.get("final_answer") or ""
        complexity = result_state.get("complexity")
        is_done = bool(result_state.get("form_submitted"))
        args = result_state.get("idea_form")

        return FlowRunResponse(
            answer=answer,
            complexity=complexity,
            isDone=is_done,
            args=args,
            trace=[],
        )

    def _build_default_llm_config(self) -> LLMProviderConfig:
        """
        Build a default LLM configuration from application settings.

        Extension points:
        - Add environment-specific defaults or safety settings.
        - Validate required API keys and base URLs.
        """

        provider = self._settings.default_provider
        if provider == "azure":
            return LLMProviderConfig(
                provider="azure",
                model=self._settings.default_azure_model,
                base_url=self._settings.azure_endpoint or "",
                api_key=self._settings.azure_api_key or "",
                azure_endpoint=self._settings.azure_endpoint,
                azure_api_version=self._settings.azure_api_version,
                azure_deployment_name=self._settings.azure_deployment_name,
                max_tokens=self._settings.llm_max_tokens,
            )
        if provider == "local":
            return LLMProviderConfig(
                provider="local",
                model=self._settings.default_local_model,
                base_url=self._settings.local_base_url,
                api_key=self._settings.local_api_key,
                max_tokens=self._settings.llm_max_tokens,
            )
        return LLMProviderConfig(
            provider="openai",
            model=self._settings.default_openai_model,
            base_url=self._settings.openai_base_url,
            api_key=self._settings.openai_api_key or "",
            max_tokens=self._settings.llm_max_tokens,
        )

    def _get_graph(self):
        """
        Build or return the cached LangGraph flow.

        Extension points:
        - Rebuild graph based on tenant-specific settings.
        """

        if self._graph is None:
            config = self._build_default_llm_config()
            self._graph = build_flow_graph(
                llm_factory=self._llm_factory,
                function_registry=self._function_registry,
                config=config,
            )
        return self._graph
