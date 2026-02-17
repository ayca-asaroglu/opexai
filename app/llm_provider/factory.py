"""
Factory for constructing chat model instances from configuration.

Extension points:
- Add retry, timeout, or logging configuration.
- Add provider-specific defaults and validation.
"""

import httpx
from langchain_openai import AzureChatOpenAI, ChatOpenAI

from app.llm_provider.models import LLMProviderConfig


class LLMFactory:
    """
    Build ChatOpenAI clients for both OpenAI and local endpoints.

    Extension points:
    - Add caching to reuse clients across flows.
    - Add structured tracing hooks for request/response metadata.
    """

    def __init__(self, ssl_verify: bool = True) -> None:
        """
        Initialize the factory with HTTP client configuration.

        Extension points:
        - Add proxy or custom transport configuration.
        """

        self._http_client = httpx.Client(verify=ssl_verify)

    def build_chat_model(self, config: LLMProviderConfig):
        """
        Create a chat model instance from the provided configuration.

        Extension points:
        - Add model-specific parameter mapping.
        - Add safe defaults for system prompts or tool settings.
        """

        if config.provider == "azure":
            return self._build_azure_chat_model(config)
        return self._build_openai_compatible_model(config)

    def _build_openai_compatible_model(self, config: LLMProviderConfig) -> ChatOpenAI:
        """
        Build a ChatOpenAI client for OpenAI-compatible endpoints.

        Extension points:
        - Add timeout or proxy settings for self-hosted endpoints.
        """

        params: dict[str, object] = {
            "model": config.model,
            "api_key": config.api_key,
            "base_url": config.base_url,
            "http_client": self._http_client,
        }
        if config.temperature is not None:
            params["temperature"] = config.temperature
        if config.max_tokens is not None:
            params["max_tokens"] = config.max_tokens
        return ChatOpenAI(**params)

    def _build_azure_chat_model(self, config: LLMProviderConfig) -> AzureChatOpenAI:
        """
        Build an AzureChatOpenAI client from Azure configuration.

        Extension points:
        - Add Azure-specific headers or retry policies.
        """

        params: dict[str, object] = {
            "api_key": config.api_key,
            "azure_endpoint": config.azure_endpoint,
            "api_version": config.azure_api_version,
            "deployment_name": config.azure_deployment_name,
            "http_client": self._http_client,
        }
        if config.temperature is not None:
            params["temperature"] = config.temperature
        if config.max_tokens is not None:
            params["max_tokens"] = config.max_tokens
        return AzureChatOpenAI(**params)
