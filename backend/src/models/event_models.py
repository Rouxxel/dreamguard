"""
#############################################################################
### Event models file
###
### @file event_models.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Pydantic models for recorded and streamed safety events.
"""

#Native imports
from typing import Any, Dict, Literal, Optional

#Third-party imports
from pydantic import BaseModel, Field

#Other files imports
from src.models.run_models import RunResponse
from src.models.safety_models import SafetyReportResponse


class SafetyEventResponse(BaseModel):
    """One decision about one action chunk and what happened to it."""

    session_id: str
    sequence: int
    timestamp: str
    source: str
    executed: bool = Field(..., description="True only when the robot played the action.")
    halted: bool
    error: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    report: SafetyReportResponse
    action: Dict[str, Any] = Field(
        default_factory=dict,
        description="Arm chunks; non-finite numbers appear as 'NaN' / 'Infinity' strings.",
    )
    current_joints: Optional[Dict[str, Any]] = None


class EventMessage(BaseModel):
    """WebSocket message carrying a safety event."""

    type: Literal["event"]
    event: SafetyEventResponse


class RunMessage(BaseModel):
    """WebSocket message carrying the current run status."""

    type: Literal["run"]
    run: RunResponse
