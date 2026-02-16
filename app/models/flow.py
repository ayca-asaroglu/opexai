"""
Pydantic models for flow orchestration requests and responses.

Extension points:
- Add branching metadata, edge definitions, or validation.
- Add schema validation for node-specific configuration.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field


class FlowNodeSpec(BaseModel):
    """
    Configuration for a single flow node.

    Extension points:
    - Add input/output schema references.
    - Add per-node execution options like retries or timeouts.
    """

    node_id: str = Field(description="Unique identifier for the node.")
    type: Literal["llm", "function", "script", "rag"] = Field(
        description="Node type used for dispatch."
    )
    name: str | None = Field(
        default=None,
        description="Optional display name for the node.",
    )
    config: dict[str, Any] = Field(
        default_factory=dict,
        description="Node-specific configuration payload.",
    )


class FlowRunRequest(BaseModel):
    """
    Request payload for running a flow.

    Extension points:
    - Add flow-level metadata or runtime overrides.
    - Add edge definitions for non-linear flows.
    """

    nodes: list[FlowNodeSpec] = Field(
        description="Ordered list of nodes to execute."
    )
    input: Any = Field(
        default_factory=dict,
        description="Initial payload for the flow.",
    )


class FlowTraceStep(BaseModel):
    """
    Trace information for a single node execution.

    Extension points:
    - Add timing metrics, errors, or resource usage.
    """

    node_id: str = Field(description="Executed node identifier.")
    node_type: str = Field(description="Executed node type name.")
    input: Any = Field(description="Input payload for the node.")
    output: Any = Field(description="Output payload from the node.")


class FlowRunResponse(BaseModel):
    """
    Response payload after running a flow.

    Extension points:
    - Add aggregated metadata or execution statistics.
    - Add structured fields for post-processing steps.
    """

    answer: Any = Field(description="User-facing answer from the flow.")
    complexity: str | None = Field(
        default=None,
        description="Estimated complexity from sizing node output.",
    )
    isDone: bool = Field(
        default=False,
        description="Whether the idea form collection is complete.",
    )
    args: dict[str, Any] | None = Field(
        default=None,
        description="Collected idea form fields from the analyst node.",
    )
    trace: list[FlowTraceStep] = Field(
        default_factory=list,
        description="Execution trace for each node.",
    )
