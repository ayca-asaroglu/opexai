"""
Pydantic models for RAG requests and responses.

Extension points:
- Add chunking configuration and embedding settings.
- Add richer source metadata for citations.
"""

from typing import Any

from pydantic import BaseModel, Field


class RAGQueryRequest(BaseModel):
    """
    Request payload for querying the RAG service.

    Extension points:
    - Add filters, collections, or reranking controls.
    """

    query: str = Field(description="User query for retrieval.")
    top_k: int = Field(default=5, description="Number of documents to retrieve.")
    filters: dict[str, Any] | None = Field(
        default=None,
        description="Optional metadata filters for retrieval.",
    )


class RAGQueryResponse(BaseModel):
    """
    Response payload for a RAG query.

    Extension points:
    - Add confidence scores or ranking details.
    """

    answer: str = Field(description="Generated answer based on retrieved context.")
    sources: list[str] = Field(
        default_factory=list,
        description="List of source identifiers or citations.",
    )
