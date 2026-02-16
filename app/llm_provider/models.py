"""
Pydantic models for LLM provider configuration.

Extension points:
- Add cost metadata, retry policies, or timeout settings.
- Add validation rules for provider-specific parameters.
"""

from typing import Literal

from pydantic import BaseModel, Field


class LLMProviderConfig(BaseModel):
    """
    Configuration required to build a ChatOpenAI client.

    Extension points:
    - Add response formatting or tool-calling defaults.
    - Add structured metadata for model capabilities.
    """

    provider: Literal["openai", "local", "azure"] = Field(
        default="openai",
        description="Provider identifier for routing and auditing.",
    )
    model: str = Field(description="Model name for the ChatOpenAI client.")
    base_url: str = Field(
        description="OpenAI-compatible base URL for the provider."
    )
    api_key: str = Field(description="API key for the provider.")
    azure_endpoint: str | None = Field(
        default=None,
        description="Azure OpenAI endpoint base URL.",
    )
    azure_api_version: str | None = Field(
        default=None,
        description="Azure OpenAI API version string.",
    )
    azure_deployment_name: str | None = Field(
        default=None,
        description="Azure deployment name for the model.",
    )
    temperature: float | None = Field(
        default=None,
        description="Sampling temperature for response variability.",
    )
    max_tokens: int | None = Field(
        default=None,
        description="Maximum tokens to generate per response.",
    )
