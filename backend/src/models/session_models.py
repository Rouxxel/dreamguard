"""
#############################################################################
### Session models file
###
### @file session_models.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Pydantic models for recorded safety sessions.
"""

#Native imports
from typing import List

#Third-party imports
from pydantic import BaseModel

#Other files imports
from src.models.event_models import SafetyEventResponse
from src.models.safety_models import MetricsSummary


class SessionSummaryResponse(BaseModel):
    session_id: str
    summary: MetricsSummary


class SessionEventsResponse(BaseModel):
    """One page of a recorded session plus the summary of the whole session."""

    session_id: str
    total: int
    offset: int
    limit: int
    events: List[SafetyEventResponse]
    summary: MetricsSummary
