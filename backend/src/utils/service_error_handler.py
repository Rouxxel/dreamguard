"""
#############################################################################
### Service error handler file
###
### @file service_error_handler.py
### @author Sebastian Russo
### @date 2026
#############################################################################

This module contains the global handler that turns service-layer errors into
JSON HTTP responses with the status code carried by each error.
"""

from fastapi import Request
from fastapi.responses import JSONResponse

from src.resources.service_errors import ServiceError
from src.utils.custom_logger import log_handler

async def service_error_handler(request: Request, exc: ServiceError):
    """
    Handles errors raised by the service layer.

    Parameters:
    request (Request): The incoming HTTP request that triggered the error.
    exc (ServiceError): The error, carrying the HTTP status code to return.

    Returns:
    JSONResponse: The status code of the error with its message as detail.
    """
    log_handler.info(f"{request.method} {request.url.path} -> {exc.status_code}: {exc}")
    return JSONResponse(status_code=exc.status_code, content={"detail": str(exc)})
