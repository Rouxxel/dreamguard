"""
#############################################################################
### Run catalog endpoint file
###
### @file get_catalog.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Lists the action sources, injectable faults, cameras and joint names.
"""

#Third-party imports
from fastapi import APIRouter, Request
from dreamguard.sources import FAULTS

#Other files imports
from src.utils.limiter import limiter as SlowLimiter
from src.core_specs.configuration.config_loader import config_loader
from src.core_specs.data.data_loader import data_loader
from src.models.run_models import CatalogResponse
from src.resources.run_service import paid_calls_allowed

"""API ROUTER-----------------------------------------------------------"""
router = APIRouter(
    prefix=config_loader["endpoints"]["get_catalog"]["endpoint_prefix"],
    tags=[config_loader["endpoints"]["get_catalog"]["endpoint_tag"]],
)

"""ENDPOINT-----------------------------------------------------------"""
@router.get(
    config_loader["endpoints"]["get_catalog"]["endpoint_route"],
    response_model=CatalogResponse,
)
@SlowLimiter.limit(
    f"{config_loader['endpoints']['get_catalog']['request_limit']}/"
    f"{config_loader['endpoints']['get_catalog']['unit_of_time_for_limit']}"
)
async def get_catalog(request: Request) -> CatalogResponse:
    """
    Get the run catalog.

    Parameters:
        request (Request): Incoming HTTP request (required by the rate limiter).

    Returns:
        CatalogResponse: Sources, faults (with descriptions), cameras, joints and
        whether paid Dream-1 calls are currently allowed.
    """
    faults = {
        fault_id: {**data_loader["faults"][fault_id], "description": description}
        for fault_id, description in FAULTS.items()
    }
    return {
        "sources": data_loader["sources"],
        "faults": faults,
        "cameras": data_loader["cameras"],
        "joint_names": data_loader["joint_names"],
        "paid_calls_allowed": paid_calls_allowed(),
    }
