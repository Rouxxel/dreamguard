"""Replays recorded action chunks through the Dream-1 client interface, at no cost.

Accepts DreamGuard session files (``JsonlSessionRecorder`` output) and Dream-1 reply fixtures:
any JSON-lines file whose lines carry an ``action`` object with ``q_r_chunk`` / ``q_l_chunk``.
"""

from __future__ import annotations

import copy
import threading
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any, Self

from ..events import read_session


class ReplayExhaustedError(RuntimeError):
    """All recorded actions have been replayed."""


class ReplayDreamClient:
    def __init__(self, actions: Sequence[Mapping[str, Any]], *, loop: bool = False) -> None:
        if not actions:
            raise ValueError("A replay needs at least one recorded action")
        self._actions = [copy.deepcopy(dict(a)) for a in actions]
        self.loop = loop
        self.index = 0
        self._lock = threading.Lock()

    @classmethod
    def from_file(cls, path: str | Path, *, loop: bool = False) -> ReplayDreamClient:
        actions = [line["action"] for line in read_session(path) if line.get("action")]
        return cls(actions, loop=loop)

    def __len__(self) -> int:
        return len(self._actions)

    # --- SDK inference surface (observations are accepted and ignored) --------------------

    def policy(self, config: Mapping[str, Any]) -> None:
        self.rewind()

    def set_observation(self, frames: Any, observation: Any, *, timestamp=None) -> None:
        return None

    def get_action(self, *, commanded: Mapping[str, Any] | None = None) -> dict[str, Any]:
        with self._lock:
            if self.index >= len(self._actions):
                if not self.loop:
                    raise ReplayExhaustedError(f"Replayed all {len(self._actions)} actions")
                self.index = 0
            action = copy.deepcopy(self._actions[self.index])
            self.index += 1
        return action

    def reset_episode(self) -> None:
        self.rewind()

    def rewind(self) -> None:
        with self._lock:
            self.index = 0

    def close(self) -> None:
        return None

    def __enter__(self) -> Self:
        return self

    def __exit__(self, *exc_info: object) -> None:
        self.close()
