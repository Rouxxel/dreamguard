"""
#############################################################################
### Camera service file
###
### @file camera_service.py
### @author Sebastian Russo
### @date 2026
#############################################################################

This module renders the simulator cameras on one background thread (a single
OpenGL context) and keeps the latest JPEG of each camera for the MJPEG stream.
If no OpenGL backend is available the service reports itself unavailable and
the rest of the backend keeps working.
"""

#Native imports
import io
import threading
import time
from typing import Optional

#Third-party imports
from PIL import Image
from dreamguard.sim import CAMERAS, SimRobot

#Other files imports
from src.utils.custom_logger import log_handler


"""CLASS-----------------------------------------------------------"""
class CameraService:  # pylint: disable=too-many-instance-attributes
    """Background renderer holding the most recent JPEG per camera role."""

    def __init__(self, robot: SimRobot, fps: float, jpeg_quality: int) -> None:
        self._robot = robot
        self._period = 1.0 / max(fps, 0.1)
        self._quality = jpeg_quality
        self._frames: dict[str, bytes] = {}
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._ready = threading.Event()
        self._thread: Optional[threading.Thread] = None
        self.error: Optional[str] = None

    @property
    def available(self) -> bool:
        return self.error is None and self._thread is not None and self._thread.is_alive()

    @property
    def period(self) -> float:
        return self._period

    def start(self, wait_seconds: float = 10.0) -> None:
        self._thread = threading.Thread(target=self._run, name="camera-renderer", daemon=True)
        self._thread.start()
        self._ready.wait(wait_seconds)

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)

    def latest(self, role: str) -> Optional[bytes]:
        with self._lock:
            return self._frames.get(role)

    def _encode(self, role: str) -> bytes:
        buffer = io.BytesIO()
        Image.fromarray(self._robot.render(role)).save(buffer, format="JPEG", quality=self._quality)
        return buffer.getvalue()

    def _run(self) -> None:
        try:
            while not self._stop.is_set():
                started = time.perf_counter()
                frames = {role: self._encode(role) for role in CAMERAS}
                with self._lock:
                    self._frames = frames
                self._ready.set()
                self._stop.wait(max(0.0, self._period - (time.perf_counter() - started)))
        except Exception as exc:  # pylint: disable=broad-exception-caught
            self.error = f"{type(exc).__name__}: {exc}"
            log_handler.warning(f"Camera rendering unavailable: {self.error}")
        finally:
            self._robot.close_thread_renderer()
            self._ready.set()
