"""
#############################################################################
### Inspect action endpoint file
###
### @file inspect_action.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Evaluates an arbitrary action against the active safety profile without
executing it.
"""

#Third-party imports
from fastapi import APIRouter, Request
from dreamguard.events import json_safe

#Other files imports
from src.utils.limiter import limiter as SlowLimiter
from src.core_specs.configuration.config_loader import config_loader
from src.models.safety_models import InspectCreate, SafetyReportResponse
from src.resources.run_service import get_manager

"""API ROUTER-----------------------------------------------------------"""
router = APIRouter(
    prefix=config_loader["endpoints"]["inspect_action"]["endpoint_prefix"],
    tags=[config_loader["endpoints"]["inspect_action"]["endpoint_tag"]],
)

"""ENDPOINT-----------------------------------------------------------"""
@router.post(
    config_loader["endpoints"]["inspect_action"]["endpoint_route"],
    response_model=SafetyReportResponse,
)
@SlowLimiter.limit(
    f"{config_loader['endpoints']['inspect_action']['request_limit']}/"
    f"{config_loader['endpoints']['inspect_action']['unit_of_time_for_limit']}"
)
async def inspect_action(request: Request, body: InspectCreate) -> SafetyReportResponse:
    """
    Inspect an action.

    Parameters:
        request (Request): Incoming HTTP request (required by the rate limiter).
        body (InspectCreate): The action and, optionally, the measured joints.

    Returns:
        SafetyReportResponse: Decision, findings and risk score. Malformed actions
        are returned as BLOCK decisions explaining why.
    """
    return json_safe(get_manager().inspect(body.action, body.current_joints))
