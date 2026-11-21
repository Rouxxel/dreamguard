"""
#############################################################################
### Camera stream endpoint file
###
### @file camera_stream.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Streams a simulator camera as MJPEG (multipart/x-mixed-replace), which a
browser can show directly in an <img> element.
"""

#Native imports
import asyncio
from typing import Optional

#Third-party imports
from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import StreamingResponse
from dreamguard.sim import CAMERAS

#Other files imports
from src.utils.limiter import limiter as SlowLimiter
from src.core_specs.configuration.config_loader import config_loader
from src.resources.run_service import get_manager

"""VARIABLES-----------------------------------------------------------"""
BOUNDARY = "frame"

"""API ROUTER-----------------------------------------------------------"""
router = APIRouter(
    prefix=config_loader["endpoints"]["camera_stream"]["endpoint_prefix"],
    tags=[config_loader["endpoints"]["camera_stream"]["endpoint_tag"]],
)

"""ENDPOINT-----------------------------------------------------------"""
@router.get(
    config_loader["endpoints"]["camera_stream"]["endpoint_route"],
    response_class=StreamingResponse,
    responses={200: {"content": {f"multipart/x-mixed-replace; boundary={BOUNDARY}": {}}}},
)
@SlowLimiter.limit(
    f"{config_loader['endpoints']['camera_stream']['request_limit']}/"
    f"{config_loader['endpoints']['camera_stream']['unit_of_time_for_limit']}"
)
async def camera_stream(
    request: Request,
    camera: str,
    max_frames: Optional[int] = Query(default=None, ge=1, le=10000),
):
    """
    Stream a camera as MJPEG.

    Parameters:
        request (Request): Incoming HTTP request (required by the rate limiter).
        camera (str): Camera role: overhead, wrist_l or wrist_r.
        max_frames (int, optional): End the stream after this many frames.

    Returns:
        StreamingResponse: JPEG frames at the configured camera rate.

    Raises:
        HTTPException: 404 for an unknown camera, 503 when rendering is unavailable.
    """
    if camera not in CAMERAS:
        raise HTTPException(status_code=404, detail=f"Unknown camera {camera!r}")
    service = get_manager().camera
    if not service.available:
        raise HTTPException(
            status_code=503, detail=f"Camera rendering unavailable: {service.error}"
        )

    async def frames():
        sent = 0
        while max_frames is None or sent < max_frames:
            jpeg = service.latest(camera)
            if jpeg is not None:
                header = (
                    f"--{BOUNDARY}\r\nContent-Type: image/jpeg\r\n"
                    f"Content-Length: {len(jpeg)}\r\n\r\n"
                ).encode("ascii")
                yield header + jpeg + b"\r\n"
                sent += 1
            if await request.is_disconnected():
                break
            await asyncio.sleep(service.period)

    return StreamingResponse(
        frames(),
        media_type=f"multipart/x-mixed-replace; boundary={BOUNDARY}",
        headers={"Cache-Control": "no-store"},
    )
