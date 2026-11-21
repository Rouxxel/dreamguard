"""
#############################################################################
### Service errors file
###
### @file service_errors.py
### @author Sebastian Russo
### @date 2026
#############################################################################

This module defines the errors raised by the service layer. Each error carries
the HTTP status code the API returns for it (see utils/service_error_handler.py).
"""


class ServiceError(Exception):
    """Base class for service-layer errors mapped to HTTP responses."""

    status_code = 400


class NotFoundError(ServiceError):
    status_code = 404


class ConflictError(ServiceError):
    status_code = 409


class PaidCallsDisabledError(ServiceError):
    status_code = 403


class NotAvailableError(ServiceError):
    status_code = 503

