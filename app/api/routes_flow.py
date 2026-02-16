"""
Flow orchestration API routes.

Extension points:
- Add flow validation, saving, and versioning endpoints.
- Add authentication or rate limiting for flow runs.
"""

from fastapi import APIRouter, Depends

from app.core.dependencies import get_orchestration_service
from app.models.flow import FlowRunRequest, FlowRunResponse
from app.orchestration.service import OrchestrationService


router = APIRouter(prefix="/flow", tags=["flow"])


@router.post("/run", response_model=FlowRunResponse)
def run_flow(
    request: FlowRunRequest,
    orchestration_service: OrchestrationService = Depends(get_orchestration_service),
) -> FlowRunResponse:
    """
    Execute an orchestration flow and return its output.

    Extension points:
    - Add request validation and audit logging.
    - Add async execution and job tracking.
    """

    return orchestration_service.run_flow(request)
