"""
RAG API routes for standalone retrieval queries.

Extension points:
- Add ingestion endpoints and collection management.
- Add authentication or rate limiting.
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_rag_service
from app.models.rag import RAGQueryRequest, RAGQueryResponse
from app.rag.service import RAGService


router = APIRouter(prefix="/rag", tags=["rag"])


@router.post("/query", response_model=RAGQueryResponse)
def query_rag(
    request: RAGQueryRequest,
    rag_service: RAGService = Depends(get_rag_service),
) -> RAGQueryResponse:
    """
    Execute a standalone RAG query and return the result.

    Extension points:
    - Add query validation, caching, or reranking.
    """

    return rag_service.query(request)
