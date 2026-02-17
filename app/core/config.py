"""
Central configuration models for the platform.

Extension points:
- Add provider-specific settings and feature flags.
- Add structured logging or tracing configuration.

Example usage:
    settings = Settings()
"""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Application configuration loaded from environment variables.

    Extension points:
    - Add provider-specific credentials or default model names.
    - Add feature flags for experimental orchestration behavior.
    """

    model_config = SettingsConfigDict(
        env_prefix="LLM_ORCH_",
        env_file=".env",
        extra="ignore",
    )

    app_name: str = "LLM Orchestration Platform"
    environment: str = "dev"
    ssl_verify: bool = True
    llm_max_tokens: int | None = None
    default_provider: str = "openai"
    default_openai_model: str = "gpt-4o"
    default_local_model: str = "llama3"
    default_azure_model: str = "gpt-4o"
    openai_api_key: str | None = None
    local_api_key: str = "dummy"
    azure_api_key: str | None = None
    openai_base_url: str = "https://api.openai.com/v1"
    local_base_url: str = "http://localhost:8000/v1"
    azure_endpoint: str | None = None
    azure_api_version: str = "2024-02-15-preview"
    azure_deployment_name: str | None = None
    rag_default_collection: str = "default"
    chroma_persist_path: str = "./.chroma"
    log_level: str = "INFO"
