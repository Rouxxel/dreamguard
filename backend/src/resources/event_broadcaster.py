"""
#############################################################################
### Event broadcaster file
###
### @file event_broadcaster.py
### @author Sebastian Russo
### @date 2026
#############################################################################

This module forwards messages produced on worker threads (safety events, run
status changes) to every connected WebSocket client. Each client owns a bounded
asyncio queue on its own event loop; when a client falls behind, its oldest
messages are dropped so a slow dashboard can never slow down supervision.
"""

#Native imports
import asyncio
import threading
from typing import Any

"""VARIABLES-----------------------------------------------------------"""
#Maximum number of pending messages per connected client
CLIENT_QUEUE_SIZE = 512


"""CLASS-----------------------------------------------------------"""
class EventBroadcaster:
    """Thread-safe fan-out of JSON-serializable messages to asyncio queues."""

    def __init__(self) -> None:
        self._clients: dict[asyncio.Queue, asyncio.AbstractEventLoop] = {}
        self._lock = threading.Lock()

    def register(self) -> asyncio.Queue:
        """Create a queue for the calling coroutine's event loop."""
        queue: asyncio.Queue = asyncio.Queue(maxsize=CLIENT_QUEUE_SIZE)
        with self._lock:
            self._clients[queue] = asyncio.get_running_loop()
        return queue

    def unregister(self, queue: asyncio.Queue) -> None:
        with self._lock:
            self._clients.pop(queue, None)

    @property
    def client_count(self) -> int:
        with self._lock:
            return len(self._clients)

    def publish(self, message: dict[str, Any]) -> None:
        """Deliver a message to every client; callable from any thread."""
        with self._lock:
            clients = list(self._clients.items())
        for queue, loop in clients:
            try:
                loop.call_soon_threadsafe(_put_dropping_oldest, queue, message)
            except RuntimeError:
                #The client's event loop is closed; forget the client
                self.unregister(queue)


def _put_dropping_oldest(queue: asyncio.Queue, message: dict[str, Any]) -> None:
    if queue.full():
        queue.get_nowait()
    queue.put_nowait(message)


"""VARIABLES-----------------------------------------------------------"""
#Shared broadcaster instance
broadcaster = EventBroadcaster()
