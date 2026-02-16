"""
Top-level API router aggregating sub-routers.

Extension points:
- Add API versioning or global dependencies.
- Mount additional routers for new domains.
"""

from fastapi import APIRouter

from app.api.routes_flow import router as flow_router
from app.api.routes_functions import router as functions_router
from app.api.routes_rag import router as rag_router


api_router = APIRouter()
api_router.include_router(flow_router)
api_router.include_router(rag_router)
api_router.include_router(functions_router)
