"""Action sources with the Dream-1 client interface (fake, replay; Dream-1 itself in Phase 7)."""

from .fake import FAULTS, FakeDreamClient
from .replay import ReplayDreamClient, ReplayExhaustedError

__all__ = ["FAULTS", "FakeDreamClient", "ReplayDreamClient", "ReplayExhaustedError"]
