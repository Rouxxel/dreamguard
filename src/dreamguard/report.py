"""Safety decisions, structured findings and risk scoring."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class Decision(str, Enum):
    APPROVE = "APPROVE"
    MODIFY = "MODIFY"  # Reserved: corrections are not enabled in the MVP.
    BLOCK = "BLOCK"


class Severity(str, Enum):
    WARNING = "warning"  # Reported and scored, but does not block.
    VIOLATION = "violation"  # Blocks the action.


# Risk contributed by a blocking finding of each check. Input and state problems score highest
# because nothing about the action can be trusted when they occur.
CHECK_WEIGHTS: dict[str, int] = {
    "action_format": 100,
    "chunk_shape": 100,
    "current_state": 100,
    "fk": 100,
    "joint_limit": 90,
    "workspace": 90,
    "separation": 90,
    "step": 80,
    "velocity": 80,
    "gripper": 70,
}
DEFAULT_VIOLATION_WEIGHT = 100
MAX_WARNING_RISK = 50


@dataclass(frozen=True)
class Finding:
    check: str
    severity: Severity
    message: str
    arm: str | None = None
    row: int | None = None
    joint: int | None = None
    value: float | None = None
    limit: float | None = None
    weight: int = 0

    @property
    def blocking(self) -> bool:
        return self.severity is Severity.VIOLATION

    def __str__(self) -> str:
        return self.message

    def as_dict(self) -> dict[str, Any]:
        return {
            "check": self.check,
            "severity": self.severity.value,
            "message": self.message,
            "arm": self.arm,
            "row": self.row,
            "joint": self.joint,
            "value": self.value,
            "limit": self.limit,
        }


def violation(check: str, message: str, **details: Any) -> Finding:
    weight = CHECK_WEIGHTS.get(check, DEFAULT_VIOLATION_WEIGHT)
    return Finding(check, Severity.VIOLATION, message, weight=weight, **details)


def warning(check: str, message: str, weight: int, **details: Any) -> Finding:
    return Finding(
        check, Severity.WARNING, message, weight=max(0, min(MAX_WARNING_RISK, weight)), **details
    )


def compute_risk(findings: tuple[Finding, ...] | list[Finding]) -> int:
    """Developer-facing heuristic in [0, 100]; not a probability of harm.

    Blocked actions score the weight of their most serious check plus 2 per additional
    violation (minimum 70). Approved actions score the strongest warning (at most 50).
    """
    violations = [f for f in findings if f.blocking]
    if violations:
        return min(100, max(f.weight for f in violations) + 2 * (len(violations) - 1))
    return max((f.weight for f in findings), default=0)


@dataclass(frozen=True)
class SafetyReport:
    decision: Decision
    risk_score: int
    findings: tuple[Finding, ...]
    checked_rows: int
    latency_ms: float = 0.0

    @classmethod
    def from_findings(
        cls, findings: list[Finding], checked_rows: int, latency_ms: float = 0.0
    ) -> SafetyReport:
        ordered = tuple(findings)
        decision = Decision.BLOCK if any(f.blocking for f in ordered) else Decision.APPROVE
        return cls(decision, compute_risk(ordered), ordered, checked_rows, latency_ms)

    @property
    def approved(self) -> bool:
        return self.decision is not Decision.BLOCK

    @property
    def violations(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if f.blocking)

    @property
    def warnings(self) -> tuple[Finding, ...]:
        return tuple(f for f in self.findings if not f.blocking)

    @property
    def messages(self) -> tuple[str, ...]:
        return tuple(f.message for f in self.findings)

    def as_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision.value,
            "approved": self.approved,
            "risk_score": self.risk_score,
            "findings": [f.as_dict() for f in self.findings],
            "checked_rows": self.checked_rows,
            "latency_ms": round(self.latency_ms, 3),
        }


class UnsafeActionError(RuntimeError):
    def __init__(self, report: SafetyReport):
        self.report = report
        reasons = "; ".join(f.message for f in report.violations)
        super().__init__("DreamGuard blocked the action: " + reasons)
