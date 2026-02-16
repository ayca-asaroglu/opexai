"""
Registry for pluggable callable tools.

Extension points:
- Add namespaces, permissions, or versioning for tools.
- Add automatic LangChain tool schema generation.
"""

from collections.abc import Callable
from typing import Any

from pydantic import BaseModel

from app.models.functions import FunctionSpec


class FunctionRegistry:
    """
    Store and expose callable tools for orchestration flows.

    Extension points:
    - Add per-tenant tool filtering or access control.
    - Add dynamic loading from configuration or plugins.
    """

    def __init__(self) -> None:
        """
        Initialize empty tool storage.

        Extension points:
        - Preload core tools or load from a registry backend.
        """

        self._functions: dict[str, Callable[..., Any]] = {}
        self._specs: dict[str, FunctionSpec] = {}
        self._schemas: dict[str, type[BaseModel] | None] = {}

    def register(
        self,
        name: str,
        func: Callable[..., Any],
        description: str,
        args_schema: type[BaseModel] | None = None,
    ) -> None:
        """
        Register a callable tool with metadata.

        Extension points:
        - Add validation for signatures and metadata.
        - Support multiple versions per tool name.
        """

        self._functions[name] = func
        self._specs[name] = FunctionSpec(name=name, description=description)
        self._schemas[name] = args_schema

    def get(self, name: str) -> Callable[..., Any]:
        """
        Retrieve a registered callable tool by name.

        Extension points:
        - Add error types or fallback behavior for missing tools.
        """

        return self._functions[name]

    def list_specs(self) -> list[FunctionSpec]:
        """
        List metadata for all registered tools.

        Extension points:
        - Add filtering or sorting options for response output.
        """

        return list(self._specs.values())

    def as_langchain_tools(self) -> list[Any]:
        """
        Convert registered tools into LangChain tool objects.

        Extension points:
        - Implement conversion using langchain_core.tools.
        - Attach tool schemas and runtime metadata.
        """

        from langchain_core.tools import StructuredTool

        tools: list[Any] = []
        for name, func in self._functions.items():
            spec = self._specs[name]
            schema = self._schemas.get(name)
            if schema is None:
                tool = StructuredTool.from_function(
                    func=func,
                    name=name,
                    description=spec.description,
                )
            else:
                tool = StructuredTool.from_function(
                    func=func,
                    name=name,
                    description=spec.description,
                    args_schema=schema,
                )
            tools.append(tool)
        return tools
