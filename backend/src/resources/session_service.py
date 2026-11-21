"""
#############################################################################
### Session service file
###
### @file session_service.py
### @author Sebastian Russo
### @date 2026
#############################################################################

This module reads recorded safety sessions (one JSONL file per session) for
the session list and replay views. Session ids are validated before they are
turned into file names, and resolved paths must stay inside the sessions
directory.
"""

#Native imports
from pathlib import Path
from typing import Any, Optional

#Third-party imports
from dreamguard.events import list_sessions, read_session, validate_session_id
from dreamguard.metrics import summarize_events

#Other files imports
from src.core_specs.configuration.config_loader import config_loader, resolve_backend_path
from src.resources.service_errors import NotFoundError, ServiceError

"""VARIABLES-----------------------------------------------------------"""
SESSIONS_DIR = Path(resolve_backend_path(config_loader["defaults"]["sessions_dir"]))
MAX_LISTED_SESSIONS = 100


"""METHODS-----------------------------------------------------------"""
def sessions_dir() -> Path:
    """Directory holding session files (read at call time so it can be reconfigured)."""
    return SESSIONS_DIR


def session_path(session_id: str, directory: Optional[Path] = None) -> Path:
    """Path of a session file; rejects invalid ids and paths escaping the directory."""
    directory = directory or sessions_dir()
    try:
        validate_session_id(session_id)
    except ValueError as exc:
        raise ServiceError(str(exc)) from exc
    root = directory.resolve()
    path = (root / f"{session_id}.jsonl").resolve()
    if path.parent != root:
        raise ServiceError(f"Invalid session id: {session_id!r}")
    return path


def _load(session_id: str, directory: Optional[Path] = None) -> list[dict[str, Any]]:
    path = session_path(session_id, directory)
    if not path.is_file():
        raise NotFoundError(f"Session {session_id} not found")
    try:
        return read_session(path)
    except ValueError as exc:
        raise ServiceError(str(exc)) from exc


def list_session_summaries(directory: Optional[Path] = None) -> list[dict[str, Any]]:
    """Newest sessions first, each with its event metrics."""
    directory = directory or sessions_dir()
    summaries = []
    for session_id in list(list_sessions(directory))[:MAX_LISTED_SESSIONS]:
        events = _load(session_id, directory)
        summaries.append({"session_id": session_id, "summary": summarize_events(events)})
    return summaries


def get_session_events(
    session_id: str, offset: int = 0, limit: int = 200, directory: Optional[Path] = None
) -> dict[str, Any]:
    """One page of a session's events plus the summary of the whole session."""
    events = _load(session_id, directory)
    return {
        "session_id": session_id,
        "total": len(events),
        "offset": offset,
        "limit": limit,
        "events": events[offset : offset + limit],
        "summary": summarize_events(events),
    }
