"""Safety events: an in-process event bus, JSONL session recording and session reading."""

from __future__ import annotations

import json
import logging
import math
import re
import threading
import uuid
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .report import SafetyReport

logger = logging.getLogger(__name__)

SESSION_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{1,64}$")
EventSubscriber = Callable[["SafetyEvent"], None]


def new_session_id() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"


def validate_session_id(session_id: str) -> str:
    """Session ids become file names, so only a safe character set is allowed."""
    if not isinstance(session_id, str) or not SESSION_ID_PATTERN.fullmatch(session_id):
        raise ValueError(f"Invalid session id: {session_id!r}")
    return session_id


def _plain(value: Any) -> Any:
    """JSON-safe copy: numpy values become Python values, and non-finite floats (which strict
    JSON cannot hold) become the strings "NaN", "Infinity" and "-Infinity"."""
    if hasattr(value, "tolist"):
        value = value.tolist()
    if isinstance(value, Mapping):
        return {str(k): _plain(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain(v) for v in value]
    if isinstance(value, float) and not math.isfinite(value):
        return "NaN" if math.isnan(value) else ("Infinity" if value > 0 else "-Infinity")
    return value


@dataclass(frozen=True)
class SafetyEvent:
    """One safety decision about one action chunk, and what happened to it."""

    session_id: str
    sequence: int
    report: SafetyReport
    executed: bool
    action: Mapping[str, Any] = field(default_factory=dict)
    current_joints: Mapping[str, Any] | None = None
    source: str = ""
    halted: bool = False
    error: str | None = None
    timestamp: str = field(default_factory=lambda: datetime.now(UTC).isoformat())

    def as_dict(self) -> dict[str, Any]:
        return {
            "session_id": self.session_id,
            "sequence": self.sequence,
            "timestamp": self.timestamp,
            "source": self.source,
            "executed": self.executed,
            "halted": self.halted,
            "error": self.error,
            "report": _plain(self.report.as_dict()),
            "action": {
                key: _plain(self.action[key])
                for key in ("q_r_chunk", "q_l_chunk")
                if key in self.action
            },
            "current_joints": _plain(self.current_joints),
        }


class EventBus:
    """Thread-safe publish/subscribe. A failing subscriber never affects the safety path."""

    def __init__(self) -> None:
        self._subscribers: list[EventSubscriber] = []
        self._lock = threading.Lock()

    def subscribe(self, subscriber: EventSubscriber) -> Callable[[], None]:
        with self._lock:
            self._subscribers.append(subscriber)

        def unsubscribe() -> None:
            with self._lock:
                if subscriber in self._subscribers:
                    self._subscribers.remove(subscriber)

        return unsubscribe

    def publish(self, event: SafetyEvent) -> None:
        with self._lock:
            subscribers = list(self._subscribers)
        for subscriber in subscribers:
            try:
                subscriber(event)
            except Exception:  # observers must never break supervision
                logger.exception("Safety event subscriber failed")


class JsonlSessionRecorder:
    """Appends every event of a session as one JSON line to ``<directory>/<session_id>.jsonl``."""

    def __init__(self, directory: str | Path) -> None:
        self.directory = Path(directory)
        self._lock = threading.Lock()

    def path_for(self, session_id: str) -> Path:
        return self.directory / f"{validate_session_id(session_id)}.jsonl"

    def __call__(self, event: SafetyEvent) -> None:
        line = json.dumps(event.as_dict(), allow_nan=False)
        path = self.path_for(event.session_id)
        with self._lock:
            self.directory.mkdir(parents=True, exist_ok=True)
            with path.open("a", encoding="utf-8") as file:
                file.write(line + "\n")


def read_session(path: str | Path) -> list[dict[str, Any]]:
    """Read a recorded session; malformed lines raise ``ValueError`` with their line number."""
    events: list[dict[str, Any]] = []
    with Path(path).open(encoding="utf-8") as file:
        for line_number, line in enumerate(file, start=1):
            if not line.strip():
                continue
            try:
                events.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{line_number}: invalid JSON event") from exc
    return events


def list_sessions(directory: str | Path) -> Sequence[str]:
    """Recorded session ids, newest file first."""
    folder = Path(directory)
    if not folder.is_dir():
        return []
    files = sorted(folder.glob("*.jsonl"), key=lambda p: p.stat().st_mtime, reverse=True)
    return [p.stem for p in files if SESSION_ID_PATTERN.fullmatch(p.stem)]
