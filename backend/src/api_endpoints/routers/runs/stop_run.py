"""
#############################################################################
### Stop run endpoint file
###
### @file stop_run.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Stops the active run; the robot stops after the row it is executing.
"""

#Third-party imports
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

#Other files imports
from src.utils.limiter import limiter as SlowLimiter
from src.core_specs.configuration.config_loader import config_loader
from src.models.run_models import RunResponse
from src.resources.run_service import get_manager

"""API ROUTER-----------------------------------------------------------"""
router = APIRouter(
    prefix=config_loader["endpoints"]["stop_run"]["endpoint_prefix"],
    tags=[config_loader["endpoints"]["stop_run"]["endpoint_tag"]],
)

"""ENDPOINT-----------------------------------------------------------"""
@router.post(
    config_loader["endpoints"]["stop_run"]["endpoint_route"],
    response_model=RunResponse,
)
@SlowLimiter.limit(
    f"{config_loader['endpoints']['stop_run']['request_limit']}/"
    f"{config_loader['endpoints']['stop_run']['unit_of_time_for_limit']}"
)
async def stop_run(request: Request, run_id: str) -> RunResponse:
    """
    Stop a run.

    Parameters:
        request (Request): Incoming HTTP request (required by the rate limiter).
        run_id (str): Id of the current run.

    Returns:
        RunResponse: Final status of the run.
    """
    return await run_in_threadpool(get_manager().stop_run, run_id)
