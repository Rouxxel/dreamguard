"""
#############################################################################
### List sessions endpoint file
###
### @file list_sessions.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Lists recorded safety sessions, newest first, with their metrics.
"""

#Native imports
from typing import List

#Third-party imports
from fastapi import APIRouter, Request
from fastapi.concurrency import run_in_threadpool

#Other files imports
from src.utils.limiter import limiter as SlowLimiter
from src.core_specs.configuration.config_loader import config_loader
from src.models.session_models import SessionSummaryResponse
from src.resources.session_service import list_session_summaries

"""API ROUTER-----------------------------------------------------------"""
router = APIRouter(
    prefix=config_loader["endpoints"]["list_sessions"]["endpoint_prefix"],
    tags=[config_loader["endpoints"]["list_sessions"]["endpoint_tag"]],
)

"""ENDPOINT-----------------------------------------------------------"""
@router.get(
    config_loader["endpoints"]["list_sessions"]["endpoint_route"],
    response_model=List[SessionSummaryResponse],
)
@SlowLimiter.limit(
    f"{config_loader['endpoints']['list_sessions']['request_limit']}/"
    f"{config_loader['endpoints']['list_sessions']['unit_of_time_for_limit']}"
)
async def list_sessions(request: Request) -> List[SessionSummaryResponse]:
    """
    List recorded sessions.

    Parameters:
        request (Request): Incoming HTTP request (required by the rate limiter).

    Returns:
        list[SessionSummaryResponse]: Up to 100 sessions with their metrics.
    """
    return await run_in_threadpool(list_session_summaries)
