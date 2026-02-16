"""
Function registry API routes.

Extension points:
- Add endpoints for registering or removing tools.
- Add authorization for sensitive tools.
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_function_registry
from app.functions.registry import FunctionRegistry
from app.models.functions import FunctionListResponse


router = APIRouter(prefix="/functions", tags=["functions"])


@router.post("/list", response_model=FunctionListResponse)
def list_functions(
    registry: FunctionRegistry = Depends(get_function_registry),
) -> FunctionListResponse:
    """
    List available function tools for orchestration.

    Extension points:
    - Add filtering, search, or pagination.
    """

    return FunctionListResponse(functions=registry.list_specs())
