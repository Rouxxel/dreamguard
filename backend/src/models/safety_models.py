"""
#############################################################################
### Safety models file
###
### @file safety_models.py
### @author Sebastian Russo
### @date 2026
#############################################################################

Pydantic models for safety reports, findings, inspection requests, the active
safety profile and session metrics.
"""

#Native imports
from typing import Any, Dict, List, Literal, Optional

#Third-party imports
from pydantic import BaseModel, Field


class FindingResponse(BaseModel):
    """One safety finding; violations block, warnings do not."""

    check: str = Field(..., description="Check that produced the finding, e.g. joint_limit.")
    severity: Literal["violation", "warning"]
    message: str
    arm: Optional[str] = None
    row: Optional[int] = None
    joint: Optional[int] = None
    value: Optional[float] = None
    limit: Optional[float] = None


class SafetyReportResponse(BaseModel):
    """DreamGuard's decision about one action chunk."""

    decision: Literal["APPROVE", "MODIFY", "BLOCK"]
    approved: bool
    risk_score: int = Field(
        ..., ge=0, le=100, description="Developer heuristic, not a probability."
    )
    findings: List[FindingResponse]
    checked_rows: int
    latency_ms: float


class InspectCreate(BaseModel):
    """An action to evaluate without executing it.

    ``action`` is intentionally untyped: malformed actions must reach the guard so it can
    explain why they are blocked, instead of being rejected by request validation.
    """

    action: Any = Field(..., description="Dream-1 action dict with q_r_chunk / q_l_chunk.")
    current_joints: Optional[Dict[str, Any]] = Field(
        default=None, description="Measured joints per arm: {'right': [6], 'left': [6]}."
    )


class ProfileResponse(BaseModel):
    """The active safety profile."""

    name: str
    forward_kinematics: bool
    max_consecutive_blocks: int
    config: Dict[str, Any]


class LatencySummary(BaseModel):
    p50: Optional[float] = None
    p95: Optional[float] = None
    max: Optional[float] = None


class MetricsSummary(BaseModel):
    """Session metrics (PRD section 13)."""

    actions_evaluated: int
    approved: int
    blocked: int
    executed: int
    halts: int
    unsafe_injected: int
    unsafe_prevented: int
    unsafe_missed: int
    false_rejections: int
    warnings: int
    violations_by_check: Dict[str, int]
    latency_ms: LatencySummary
    sources: List[str]
    first_timestamp: Optional[str] = None
    last_timestamp: Optional[str] = None


class MetricsResponse(BaseModel):
    run_id: Optional[str] = None
    summary: MetricsSummary
