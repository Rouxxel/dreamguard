"""
#############################################################################
### Safety profile endpoint file
###
### @file get_profile.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Returns the active safety profile (limits used for every decision).
"""

#Third-party imports
from fastapi import APIRouter, Request

#Other files imports
from src.utils.limiter import limiter as SlowLimiter
from src.core_specs.configuration.config_loader import config_loader
from src.models.safety_models import ProfileResponse
from src.resources.run_service import get_manager

"""API ROUTER-----------------------------------------------------------"""
router = APIRouter(
    prefix=config_loader["endpoints"]["get_profile"]["endpoint_prefix"],
    tags=[config_loader["endpoints"]["get_profile"]["endpoint_tag"]],
)

"""ENDPOINT-----------------------------------------------------------"""
@router.get(
    config_loader["endpoints"]["get_profile"]["endpoint_route"],
    response_model=ProfileResponse,
)
@SlowLimiter.limit(
    f"{config_loader['endpoints']['get_profile']['request_limit']}/"
    f"{config_loader['endpoints']['get_profile']['unit_of_time_for_limit']}"
)
async def get_profile(request: Request) -> ProfileResponse:
    """
    Get the active safety profile.

    Parameters:
        request (Request): Incoming HTTP request (required by the rate limiter).

    Returns:
        ProfileResponse: Profile name and its SafetyConfig values.
    """
    return get_manager().profile_info()
