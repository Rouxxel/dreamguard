"""
#############################################################################
### Reset run endpoint file
###
### @file reset_run.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Resumes a run that halted after repeated blocked actions, once an operator
has reviewed why the actions were blocked.
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
    prefix=config_loader["endpoints"]["reset_run"]["endpoint_prefix"],
    tags=[config_loader["endpoints"]["reset_run"]["endpoint_tag"]],
)

"""ENDPOINT-----------------------------------------------------------"""
@router.post(
    config_loader["endpoints"]["reset_run"]["endpoint_route"],
    response_model=RunResponse,
)
@SlowLimiter.limit(
    f"{config_loader['endpoints']['reset_run']['request_limit']}/"
    f"{config_loader['endpoints']['reset_run']['unit_of_time_for_limit']}"
)
async def reset_run(request: Request, run_id: str) -> RunResponse:
    """
    Clear the halt of a run.

    Parameters:
        request (Request): Incoming HTTP request (required by the rate limiter).
        run_id (str): Id of the current, halted run.

    Returns:
        RunResponse: Status of the resumed run (409 if it is not halted).
    """
    return get_manager().reset_run(run_id)
