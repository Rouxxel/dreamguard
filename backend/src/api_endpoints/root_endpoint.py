"""
#############################################################################
### Root endpoint file
###
### @file root_endpoint.py
### @Sebastian Russo
### @date: 2025
#############################################################################

This module contains an endpoint that simply returns a dictionary confirming
the backend is up and running correctly. It serves as a health check and
does not perform any other operation.
"""

#Native imports
import importlib.util

#Third-party imports
from fastapi import APIRouter, Request

#Other files imports
from src.utils.custom_logger import log_handler
from src.utils.limiter import limiter as SlowLimiter
from src.core_specs.configuration.config_loader import config_loader
from src.resources.run_service import get_manager, paid_calls_allowed
from src.resources.service_errors import NotAvailableError

"""API ROUTER-----------------------------------------------------------"""
# Get API router
router = APIRouter(
    prefix=config_loader['endpoints']['root_directory_endpoint']['endpoint_prefix'],
    tags=[config_loader['endpoints']['root_directory_endpoint']['endpoint_tag']],
)

"""ENDPOINT-----------------------------------------------------------"""
# Check if app works
@router.get(config_loader['endpoints']['root_directory_endpoint']['endpoint_route'])
@SlowLimiter.limit(
    f"{config_loader['endpoints']['root_directory_endpoint']['request_limit']}/"
    f"{config_loader['endpoints']['root_directory_endpoint']['unit_of_time_for_limit']}"
)  # Root endpoint rate limit
async def root_endpoint(request: Request):
    """
    Root endpoint to verify that the API is operational.

    This endpoint serves as a basic health check and confirms that the application
    is running correctly. It is rate-limited according to the configuration.

    Parameters:
        request (Request): The incoming HTTP request for limit event management.

    Returns:
        dict: A JSON response indicating that the API is running, plus the state of
        the simulator, camera rendering, the Dream SDK and the paid-call switch.
    
    Note:
        If the rate limit is exceeded, the rate_limit_handler() function handles the response.
    """
    log_handler.debug("Backend running successfully")
    try:
        manager = get_manager()
        simulator, camera = "running", "available" if manager.camera.available else "unavailable"
        run_state = manager.status()["state"]
    except NotAvailableError:
        simulator, camera, run_state = "unavailable", "unavailable", None
    return {
        "status": "ok",
        "service": "dreamguard-backend",
        "message": "Backend running successfully, ready to use other endpoints",
        "simulator": simulator,
        "camera": camera,
        "run_state": run_state,
        "dream_sdk": "installed" if importlib.util.find_spec("dream") else "missing",
        "paid_calls_allowed": paid_calls_allowed(),
    }
