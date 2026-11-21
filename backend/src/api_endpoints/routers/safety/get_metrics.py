"""
#############################################################################
### Metrics endpoint file
###
### @file get_metrics.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Returns the metrics of the current (or most recent) run.
"""

#Third-party imports
from fastapi import APIRouter, Request

#Other files imports
from src.utils.limiter import limiter as SlowLimiter
from src.core_specs.configuration.config_loader import config_loader
from src.models.safety_models import MetricsResponse
from src.resources.run_service import get_manager

"""API ROUTER-----------------------------------------------------------"""
router = APIRouter(
    prefix=config_loader["endpoints"]["get_metrics"]["endpoint_prefix"],
    tags=[config_loader["endpoints"]["get_metrics"]["endpoint_tag"]],
)

"""ENDPOINT-----------------------------------------------------------"""
@router.get(
    config_loader["endpoints"]["get_metrics"]["endpoint_route"],
    response_model=MetricsResponse,
)
@SlowLimiter.limit(
    f"{config_loader['endpoints']['get_metrics']['request_limit']}/"
    f"{config_loader['endpoints']['get_metrics']['unit_of_time_for_limit']}"
)
async def get_metrics(request: Request) -> MetricsResponse:
    """
    Get run metrics.

    Parameters:
        request (Request): Incoming HTTP request (required by the rate limiter).

    Returns:
        MetricsResponse: Counts, unsafe-action outcomes, false rejections and latency.
    """
    return get_manager().metrics()
