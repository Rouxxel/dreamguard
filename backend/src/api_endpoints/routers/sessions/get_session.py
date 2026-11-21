"""
#############################################################################
### Get session endpoint file
###
### @file get_session.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Returns one page of a recorded session's safety events, for replay.
"""

#Third-party imports
from fastapi import APIRouter, Request, Query
from fastapi.concurrency import run_in_threadpool

#Other files imports
from src.utils.limiter import limiter as SlowLimiter
from src.core_specs.configuration.config_loader import config_loader
from src.models.session_models import SessionEventsResponse
from src.resources.session_service import get_session_events

"""API ROUTER-----------------------------------------------------------"""
router = APIRouter(
    prefix=config_loader["endpoints"]["get_session"]["endpoint_prefix"],
    tags=[config_loader["endpoints"]["get_session"]["endpoint_tag"]],
)

"""ENDPOINT-----------------------------------------------------------"""
@router.get(
    config_loader["endpoints"]["get_session"]["endpoint_route"],
    response_model=SessionEventsResponse,
)
@SlowLimiter.limit(
    f"{config_loader['endpoints']['get_session']['request_limit']}/"
    f"{config_loader['endpoints']['get_session']['unit_of_time_for_limit']}"
)
async def get_session(
    request: Request,
    session_id: str,
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=200, ge=1, le=1000),
) -> SessionEventsResponse:
    """
    Get a page of a recorded session.

    Parameters:
        request (Request): Incoming HTTP request (required by the rate limiter).
        session_id (str): Session id (validated; must be a recorded session).
        offset (int): Index of the first event.
        limit (int): Maximum number of events.

    Returns:
        SessionEventsResponse: The events and the summary of the whole session.
    """
    return await run_in_threadpool(get_session_events, session_id, offset, limit)
