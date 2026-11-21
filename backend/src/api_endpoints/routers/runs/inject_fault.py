"""
#############################################################################
### Inject fault endpoint file
###
### @file inject_fault.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Makes the next action chunk of a scripted run unsafe in a catalogued way, to
demonstrate that DreamGuard blocks it.
"""

#Third-party imports
from fastapi import APIRouter, Request

#Other files imports
from src.utils.limiter import limiter as SlowLimiter
from src.core_specs.configuration.config_loader import config_loader
from src.models.run_models import FaultCreate, FaultResponse
from src.resources.run_service import get_manager

"""API ROUTER-----------------------------------------------------------"""
router = APIRouter(
    prefix=config_loader["endpoints"]["inject_fault"]["endpoint_prefix"],
    tags=[config_loader["endpoints"]["inject_fault"]["endpoint_tag"]],
)

"""ENDPOINT-----------------------------------------------------------"""
@router.post(
    config_loader["endpoints"]["inject_fault"]["endpoint_route"],
    response_model=FaultResponse,
    status_code=202,
)
@SlowLimiter.limit(
    f"{config_loader['endpoints']['inject_fault']['request_limit']}/"
    f"{config_loader['endpoints']['inject_fault']['unit_of_time_for_limit']}"
)
async def inject_fault(request: Request, run_id: str, body: FaultCreate) -> FaultResponse:
    """
    Inject a fault into the next chunk.

    Parameters:
        request (Request): Incoming HTTP request (required by the rate limiter).
        run_id (str): Id of the current, running scripted run.
        body (FaultCreate): Fault id from the catalog.

    Returns:
        FaultResponse: The accepted fault and its description.
    """
    return get_manager().inject_fault(run_id, body.fault)
