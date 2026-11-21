"""
#############################################################################
### Current run endpoint file
###
### @file get_current_run.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Returns the status of the current (or most recent) run.
"""

#Third-party imports
from fastapi import APIRouter, Request

#Other files imports
from src.utils.limiter import limiter as SlowLimiter
from src.core_specs.configuration.config_loader import config_loader
from src.models.run_models import RunResponse
from src.resources.run_service import get_manager

"""API ROUTER-----------------------------------------------------------"""
router = APIRouter(
    prefix=config_loader["endpoints"]["get_current_run"]["endpoint_prefix"],
    tags=[config_loader["endpoints"]["get_current_run"]["endpoint_tag"]],
)

"""ENDPOINT-----------------------------------------------------------"""
@router.get(
    config_loader["endpoints"]["get_current_run"]["endpoint_route"],
    response_model=RunResponse,
)
@SlowLimiter.limit(
    f"{config_loader['endpoints']['get_current_run']['request_limit']}/"
    f"{config_loader['endpoints']['get_current_run']['unit_of_time_for_limit']}"
)
async def get_current_run(request: Request) -> RunResponse:
    """
    Get the current run status.

    Parameters:
        request (Request): Incoming HTTP request (required by the rate limiter).

    Returns:
        RunResponse: Run status; state is idle when no run has been started.
    """
    return get_manager().status()
