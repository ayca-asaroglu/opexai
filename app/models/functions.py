"""
Pydantic models for function registry API responses.

Extension points:
- Add tool schemas, versioning, or parameter metadata.
"""

from pydantic import BaseModel, Field


class FunctionSpec(BaseModel):
    """
    Metadata describing a registered tool function.

    Extension points:
    - Add parameter schemas or usage examples.
    """

    name: str = Field(description="Tool name for invocation.")
    description: str = Field(description="Tool description for discovery.")


class FunctionListResponse(BaseModel):
    """
    Response payload listing all registered tools.

    Extension points:
    - Add pagination or grouping by namespace.
    """

    functions: list[FunctionSpec] = Field(
        default_factory=list,
        description="List of registered tool metadata.",
    )
