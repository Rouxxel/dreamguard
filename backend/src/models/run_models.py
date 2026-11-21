"""
#############################################################################
### Run models file
###
### @file run_models.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Pydantic models for simulation runs, fault injection and the run catalog.
"""

#Native imports
from typing import Dict, List, Literal, Optional

#Third-party imports
from pydantic import BaseModel, Field

RunSource = Literal["fake", "replay", "dream1"]
RunState = Literal["idle", "running", "halted", "stopped", "completed", "error"]


class RunBase(BaseModel):
    """Fields shared by run requests and responses."""

    source: RunSource = Field(..., description="Where action chunks come from.")
    prompt: str = Field(
        default="", max_length=500, description="Task prompt sent with observations."
    )


class RunCreate(RunBase):
    """POST body to start a run."""

    max_chunks: Optional[int] = Field(
        default=None, ge=1, description="Stop after this many chunks (capped by configuration)."
    )
    replay_session_id: Optional[str] = Field(
        default=None, description="Recorded session to replay (replay source only)."
    )


class RunResponse(BaseModel):
    """Current run status; ``run_id`` is also the session id of its recording."""

    run_id: Optional[str] = None
    state: RunState
    source: Optional[RunSource] = None
    prompt: str = ""
    chunks: int = 0
    rows_played: int = 0
    consecutive_blocks: int = 0
    paid_calls: int = 0
    started_at: Optional[str] = None
    finished_at: Optional[str] = None
    error: Optional[str] = None
    replay_session_id: Optional[str] = None


class FaultCreate(BaseModel):
    """POST body to inject a fault into the next chunk of a scripted run."""

    fault: str = Field(..., description="Fault id from the catalog, e.g. joint_limit.")


class FaultResponse(BaseModel):
    run_id: str
    fault: str
    description: str


class SourceInfo(BaseModel):
    label: str
    description: str
    paid: bool


class FaultInfo(BaseModel):
    label: str
    description: str
    expected_check: str


class CatalogResponse(BaseModel):
    """Sources, faults, cameras and joints the dashboard can offer."""

    sources: Dict[str, SourceInfo]
    faults: Dict[str, FaultInfo]
    cameras: Dict[str, str]
    joint_names: List[str]
    paid_calls_allowed: bool
