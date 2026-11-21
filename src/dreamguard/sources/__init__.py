"""Action sources with the Dream-1 client interface: fake (scripted), replay and live Dream-1."""

from . import dream1
from .fake import FAULTS, FakeDreamClient
from .replay import ReplayDreamClient, ReplayExhaustedError

__all__ = ["FAULTS", "FakeDreamClient", "ReplayDreamClient", "ReplayExhaustedError", "dream1"]
