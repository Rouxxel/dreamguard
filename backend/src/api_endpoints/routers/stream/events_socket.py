"""
#############################################################################
### Events socket endpoint file
###
### @file events_socket.py
### @author Sebastian Russo
### @date 2026
#############################################################################

WebSocket that streams every safety decision and run status change live to the
dashboard. Messages are JSON: {"type": "run", "run": {...}} (sent on connect and
on every status change) and {"type": "event", "event": {...}} per decision.

WebSockets are not covered by CORS or SlowAPI, so the Origin header is checked
against the configured dashboard origins (or the backend's own origin).
"""

#Third-party imports
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

#Other files imports
from src.core_specs.configuration.config_loader import config_loader
from src.resources.event_broadcaster import broadcaster
from src.resources.run_service import get_manager
from src.utils.custom_logger import log_handler

"""API ROUTER-----------------------------------------------------------"""
router = APIRouter(
    prefix=config_loader["endpoints"]["events_socket"]["endpoint_prefix"],
    tags=[config_loader["endpoints"]["events_socket"]["endpoint_tag"]],
)

"""METHODS-----------------------------------------------------------"""
def origin_allowed(websocket: WebSocket) -> bool:
    """Allow non-browser clients (no Origin), the dashboard origins and same-origin pages."""
    origin = websocket.headers.get("origin")
    if origin is None:
        return True
    host = websocket.headers.get("host", "")
    same_origin = origin in (f"http://{host}", f"https://{host}")
    return same_origin or origin in config_loader["network"]["cors_origins"]


"""ENDPOINT-----------------------------------------------------------"""
@router.websocket(config_loader["endpoints"]["events_socket"]["endpoint_route"])
async def events_socket(websocket: WebSocket):
    """
    Stream safety events and run status changes.

    Parameters:
        websocket (WebSocket): The client connection.

    Note:
        Connections from origins that are not allowed are closed with code 1008.
        Slow clients drop their oldest pending messages instead of slowing the run.
    """
    if not origin_allowed(websocket):
        log_handler.warning(f"Rejected events socket from origin {websocket.headers.get('origin')}")
        await websocket.close(code=1008)
        return
    await websocket.accept()
    queue = broadcaster.register()
    try:
        await websocket.send_json({"type": "run", "run": get_manager().status()})
        while True:
            await websocket.send_json(await queue.get())
    except WebSocketDisconnect:
        pass
    finally:
        broadcaster.unregister(queue)
