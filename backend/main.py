"""
#############################################################################
### Main backend file
###
### @file main.py
### @author Sebastian Russo
### @date 2025
#############################################################################

This module initializes the DreamGuard FastAPI backend.
It sets up routers, custom logger, rate limiter, CORS and loads environment variables.
"""

#Native imports
import os
from contextlib import asynccontextmanager

#Third-party imports
import uvicorn
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from slowapi.errors import RateLimitExceeded
from dotenv import load_dotenv

#Json files
from src.core_specs.configuration.config_loader import config_loader, resolve_backend_path

#Load the repository-level .env before modules that read environment variables
load_dotenv(resolve_backend_path(config_loader["defaults"]["env_file_path"]))

#Other files imports
from src.utils.request_limiter import rate_limit_handler
from src.utils.service_error_handler import service_error_handler
from src.utils.custom_logger import log_handler
from src.utils.limiter import limiter
from src.core_specs.data.data_loader import data_loader

#Resources imports
from src.resources import run_service
from src.resources.service_errors import ServiceError

#Endpoints imports
from src.api_endpoints.root_endpoint import router as root_router
from src.api_endpoints.routers.runs.start_run import router as start_run_router
from src.api_endpoints.routers.runs.stop_run import router as stop_run_router
from src.api_endpoints.routers.runs.reset_run import router as reset_run_router
from src.api_endpoints.routers.runs.inject_fault import router as inject_fault_router
from src.api_endpoints.routers.runs.get_current_run import router as get_current_run_router
from src.api_endpoints.routers.runs.get_catalog import router as get_catalog_router
from src.api_endpoints.routers.sessions.list_sessions import router as list_sessions_router
from src.api_endpoints.routers.sessions.get_session import router as get_session_router
from src.api_endpoints.routers.safety.get_profile import router as get_profile_router
from src.api_endpoints.routers.safety.inspect_action import router as inspect_action_router
from src.api_endpoints.routers.safety.get_metrics import router as get_metrics_router
from src.api_endpoints.routers.stream.events_socket import router as events_socket_router
from src.api_endpoints.routers.stream.camera_stream import router as camera_stream_router

"""API APP-----------------------------------------------------------"""
#Lifespan event manager (startup and shutdown)
@asynccontextmanager
async def lifespan(app: FastAPI):
    port = config_loader["network"]["server_port"]
    log_handler.info(f"DreamGuard backend starting on port {port}")
    log_handler.debug(f"Loaded data: {data_loader}")
    run_service.startup()
    yield
    run_service.shutdown()
    log_handler.info("DreamGuard backend shutting down")

#Create FastAPI app
app = FastAPI(
    lifespan=lifespan,
    title=os.getenv("API_TITLE", "DreamGuard API"),
    version=os.getenv("API_VERSION", "0.1.0"),
    description=os.getenv(
        "API_DESCRIPTION", "Safety supervisor backend for Dream-1 robot actions"
    ),
)

"""VARIOUS-----------------------------------------------------------"""
#Setup rate limiter
app.state.limiter = limiter

#Add global exception handler for rate limits
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

#Map service-layer errors (not found, conflict, paid calls disabled...) to HTTP responses
app.add_exception_handler(ServiceError, service_error_handler)

#Allow the dashboard origins configured in config_file.json
app.add_middleware(
    CORSMiddleware,
    allow_origins=config_loader["network"]["cors_origins"],
    allow_credentials=False,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

"""Routers-----------------------------------------------------------"""
#Root
app.include_router(root_router)

#Runs (catalog and current are registered before the /{run_id} routes)
app.include_router(get_catalog_router)
app.include_router(get_current_run_router)
app.include_router(start_run_router)
app.include_router(stop_run_router)
app.include_router(reset_run_router)
app.include_router(inject_fault_router)

#Sessions
app.include_router(list_sessions_router)
app.include_router(get_session_router)

#Safety
app.include_router(get_profile_router)
app.include_router(inspect_action_router)
app.include_router(get_metrics_router)

#Streams
app.include_router(events_socket_router)
app.include_router(camera_stream_router)

"""Start server-----------------------------------------------------------"""
if __name__ == "__main__":
    uvicorn.run(
        config_loader["network"]["uvicorn_app_reference"],
        host=config_loader["network"]["host"],
        port=config_loader["network"]["server_port"],
        reload=config_loader["network"]["reload"],
        workers=config_loader["network"]["workers"],
        proxy_headers=config_loader["network"]["proxy_headers"]
    )
    #available at: http://127.0.0.1:8000/docs
