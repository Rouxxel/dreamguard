"""
#############################################################################
### Start run endpoint file
###
### @file start_run.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Starts a simulation run: the Dream-1 control loop runs on a worker thread and
every action chunk is checked by DreamGuard before it reaches the simulator.
"""

#Third-party imports
from fastapi import APIRouter, Request

#Other files imports
from src.utils.limiter import limiter as SlowLimiter
from src.core_specs.configuration.config_loader import config_loader
from src.models.run_models import RunCreate, RunResponse
from src.resources.run_service import get_manager
from src.utils.custom_logger import log_handler

"""API ROUTER-----------------------------------------------------------"""
router = APIRouter(
    prefix=config_loader["endpoints"]["start_run"]["endpoint_prefix"],
    tags=[config_loader["endpoints"]["start_run"]["endpoint_tag"]],
)

"""ENDPOINT-----------------------------------------------------------"""
@router.post(
    config_loader["endpoints"]["start_run"]["endpoint_route"],
    response_model=RunResponse,
    status_code=201,
)
@SlowLimiter.limit(
    f"{config_loader['endpoints']['start_run']['request_limit']}/"
    f"{config_loader['endpoints']['start_run']['unit_of_time_for_limit']}"
)
async def start_run(request: Request, body: RunCreate) -> RunResponse:
    """
    Start a run with the scripted (fake), replay or Dream-1 source.

    Parameters:
        request (Request): Incoming HTTP request (required by the rate limiter).
        body (RunCreate): Source, prompt, optional chunk limit and replay session.

    Returns:
        RunResponse: Status of the started run (its run_id is the session id).

    Note:
        The dream1 source is refused (403) unless paid calls are enabled in both
        config_file.json and .env. Only one run can be active (409 otherwise).
    """
    log_handler.info(f"Start run requested (source={body.source})")
    return get_manager().start_run(
        body.source, body.prompt, body.max_chunks, body.replay_session_id
    )
